"""The deterministic Control Engine.

For every transaction lifecycle bundle, this module independently
recomputes the six control dimensions required by the FinTrace control
loop:

1. lifecycle completeness   - are all required stages present?
2. amount integrity         - does order amount match payment amount?
3. refund consistency       - if a refund exists, was it honoured downstream?
4. duplicate / orphan       - are there duplicated or orphaned stage events?
5. settlement timing        - did each stage happen within its SLA window?
6. settlement consistency   - does the actual settlement match a freshly
                              recomputed expected settlement?

Every number here is a ``decimal.Decimal`` computed in plain Python - the
AI agent never touches this module and never influences its output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

from app.finance.constants import (
    AMOUNT_TOLERANCE,
    BANK_CREDIT_SLA_DAYS,
    DEFAULT_FEE_RATE,
    DEFAULT_TAX_RATE,
    SETTLEMENT_SLA_DAYS,
)
from app.finance.lifecycle_builder import LifecycleBundle
from app.finance.money import abs_diff, quantize, sum_decimals, to_decimal, within_tolerance

REQUIRED_STAGE_ORDER = ["order", "payment", "settlement", "bank_entry"]


@dataclass
class ControlResult:
    transaction_id: str

    lifecycle_completeness_ok: bool = True
    missing_stages: List[str] = field(default_factory=list)

    amount_integrity_ok: bool = True
    amount_integrity_diff: Decimal = Decimal("0.00")

    refund_present: bool = False
    refund_consistency_ok: bool = True
    refund_consistency_diff: Decimal = Decimal("0.00")

    duplicate_detected: bool = False
    duplicate_details: List[dict] = field(default_factory=list)

    orphan_detected: bool = False
    orphan_details: List[dict] = field(default_factory=list)

    settlement_timing_ok: bool = True
    settlement_days_late: int = 0
    bank_days_late: int = 0

    settlement_consistency_ok: bool = True
    settlement_consistency_diff: Decimal = Decimal("0.00")
    computed_expected_settlement: Decimal = Decimal("0.00")

    def is_fully_healthy(self) -> bool:
        return (
            self.lifecycle_completeness_ok
            and self.amount_integrity_ok
            and self.refund_consistency_ok
            and not self.duplicate_detected
            and not self.orphan_detected
            and self.settlement_timing_ok
            and self.settlement_consistency_ok
        )

    def evidence(self) -> dict:
        """A JSON-serializable snapshot used as ``control_evidence`` on the
        persisted Exception row and shown in the lifecycle trace UI."""
        return {
            "lifecycle_completeness_ok": self.lifecycle_completeness_ok,
            "missing_stages": self.missing_stages,
            "amount_integrity_ok": self.amount_integrity_ok,
            "amount_integrity_diff": str(self.amount_integrity_diff),
            "refund_present": self.refund_present,
            "refund_consistency_ok": self.refund_consistency_ok,
            "refund_consistency_diff": str(self.refund_consistency_diff),
            "duplicate_detected": self.duplicate_detected,
            "duplicate_details": self.duplicate_details,
            "orphan_detected": self.orphan_detected,
            "orphan_details": self.orphan_details,
            "settlement_timing_ok": self.settlement_timing_ok,
            "settlement_days_late": self.settlement_days_late,
            "bank_days_late": self.bank_days_late,
            "settlement_consistency_ok": self.settlement_consistency_ok,
            "settlement_consistency_diff": str(self.settlement_consistency_diff),
            "computed_expected_settlement": str(self.computed_expected_settlement),
        }


def _check_completeness(bundle: LifecycleBundle) -> tuple[bool, List[str]]:
    missing: List[str] = []
    if bundle.transaction.order is None:
        missing.append("order")
    if not any(not p.is_orphan for p in bundle.payments):
        missing.append("payment")
    if not any(not s.is_orphan for s in bundle.settlements):
        missing.append("settlement")
    if not any(not b.is_orphan for b in bundle.bank_entries):
        missing.append("bank_entry")
    return (len(missing) == 0, missing)


def _check_duplicates(bundle: LifecycleBundle) -> tuple[bool, List[dict]]:
    details: List[dict] = []
    if len(bundle.payments) > 1:
        details.append({"stage": "payment", "count": len(bundle.payments)})
    if len(bundle.settlements) > 1:
        details.append({"stage": "settlement", "count": len(bundle.settlements)})
    if len(bundle.bank_entries) > 1:
        details.append({"stage": "bank_entry", "count": len(bundle.bank_entries)})
    return (len(details) > 0, details)


def _check_orphans(bundle: LifecycleBundle) -> tuple[bool, List[dict]]:
    details: List[dict] = []
    for p in bundle.payments:
        if p.is_orphan:
            details.append({"stage": "payment", "id": p.payment_id, "amount": str(p.amount)})
    for s in bundle.settlements:
        if s.is_orphan:
            details.append({"stage": "settlement", "id": s.settlement_id, "amount": str(s.actual_settlement)})
    for b in bundle.bank_entries:
        if b.is_orphan:
            details.append({"stage": "bank_entry", "id": b.bank_entry_id, "amount": str(b.amount)})
    return (len(details) > 0, details)


def _primary_non_orphan(items: list):
    non_orphan = [i for i in items if not getattr(i, "is_orphan", False)]
    return non_orphan[0] if non_orphan else None


def run_controls(bundle: LifecycleBundle) -> ControlResult:
    """Run all six deterministic control checks for one transaction."""
    txn = bundle.transaction
    result = ControlResult(transaction_id=txn.transaction_id)

    # 1. Lifecycle completeness
    completeness_ok, missing = _check_completeness(bundle)
    result.lifecycle_completeness_ok = completeness_ok
    result.missing_stages = missing

    order_amount = to_decimal(txn.order.amount) if txn.order else Decimal("0.00")
    primary_payment = _primary_non_orphan(bundle.payments)
    payment_amount = to_decimal(primary_payment.amount) if primary_payment else Decimal("0.00")

    # 2. Amount integrity: order amount must equal payment amount.
    result.amount_integrity_diff = abs_diff(order_amount, payment_amount)
    result.amount_integrity_ok = within_tolerance(order_amount, payment_amount)

    refund_amount = sum_decimals([r.amount for r in bundle.refunds])
    result.refund_present = refund_amount > Decimal("0.00")

    primary_settlement = _primary_non_orphan(bundle.settlements)

    # 6. Settlement consistency: recompute the expected settlement fresh,
    # net of any refund, using the platform's standard fee/tax rates -
    # completely independent of whatever was stored on the Settlement row.
    net_base = payment_amount - refund_amount
    if net_base < Decimal("0.00"):
        net_base = Decimal("0.00")
    fee = quantize(net_base * DEFAULT_FEE_RATE)
    tax = quantize(fee * DEFAULT_TAX_RATE)
    expected_settlement = quantize(net_base - fee - tax)
    result.computed_expected_settlement = expected_settlement

    if primary_settlement is not None:
        actual_settlement = to_decimal(primary_settlement.actual_settlement)
        diff = abs_diff(expected_settlement, actual_settlement)
        consistency_ok = diff <= AMOUNT_TOLERANCE
    else:
        diff = Decimal("0.00")
        consistency_ok = True  # no settlement yet -> reported via completeness/missing-downstream

    result.settlement_consistency_diff = diff
    result.settlement_consistency_ok = consistency_ok

    # 3. Refund consistency: only meaningful when a refund actually exists.
    if result.refund_present:
        result.refund_consistency_diff = diff
        result.refund_consistency_ok = consistency_ok
    else:
        result.refund_consistency_diff = Decimal("0.00")
        result.refund_consistency_ok = True

    # 4. Duplicate / orphan relationships.
    dup_detected, dup_details = _check_duplicates(bundle)
    result.duplicate_detected = dup_detected
    result.duplicate_details = dup_details

    orphan_detected, orphan_details = _check_orphans(bundle)
    result.orphan_detected = orphan_detected
    result.orphan_details = orphan_details

    # 5. Settlement timing.
    primary_bank = _primary_non_orphan(bundle.bank_entries)
    settlement_days_late = 0
    bank_days_late = 0
    timing_ok = True

    if primary_payment is not None and primary_settlement is not None:
        settlement_days_late = max(
            0, (primary_settlement.settlement_timestamp - primary_payment.payment_timestamp).days
        )
        if settlement_days_late > SETTLEMENT_SLA_DAYS:
            timing_ok = False

    if primary_settlement is not None and primary_bank is not None:
        bank_days_late = max(
            0, (primary_bank.bank_timestamp - primary_settlement.settlement_timestamp).days
        )
        if bank_days_late > BANK_CREDIT_SLA_DAYS:
            timing_ok = False

    result.settlement_days_late = settlement_days_late
    result.bank_days_late = bank_days_late
    result.settlement_timing_ok = timing_ok

    return result
