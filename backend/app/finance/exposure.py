"""Deterministic financial exposure quantification.

Given a control result and the exception_type the classifier selected,
this module computes exactly how many Rupees are at risk. This is the
number that drives severity and the benchmark's "total financial
exposure" metric - it is always a plain ``Decimal`` calculation.
"""
from __future__ import annotations

from decimal import Decimal

from app.finance.control_engine import ControlResult
from app.finance.lifecycle_builder import LifecycleBundle
from app.finance.money import sum_decimals, to_decimal


def compute_financial_exposure(
    bundle: LifecycleBundle, control: ControlResult, exception_type: str | None
) -> Decimal:
    """Return the Decimal financial exposure for the given exception type.
    Returns Decimal('0.00') for a healthy (exception_type is None) result.
    """
    if exception_type is None:
        return Decimal("0.00")

    if exception_type == "duplicate_financial_event":
        extra_payments = to_decimal(sum_decimals([p.amount for p in bundle.payments[1:]]))
        extra_settlements = to_decimal(sum_decimals([s.actual_settlement for s in bundle.settlements[1:]]))
        extra_bank = to_decimal(sum_decimals([b.amount for b in bundle.bank_entries[1:]]))
        return sum_decimals([extra_payments, extra_settlements, extra_bank])

    if exception_type == "orphan_financial_event":
        orphan_payments = sum_decimals([p.amount for p in bundle.payments if p.is_orphan])
        orphan_settlements = sum_decimals([s.actual_settlement for s in bundle.settlements if s.is_orphan])
        orphan_bank = sum_decimals([b.amount for b in bundle.bank_entries if b.is_orphan])
        return sum_decimals([orphan_payments, orphan_settlements, orphan_bank])

    if exception_type in ("refund_closure_failure", "settlement_amount_discrepancy"):
        return control.settlement_consistency_diff

    if exception_type == "missing_downstream_event":
        if bundle.settlements and any(not s.is_orphan for s in bundle.settlements):
            settlement = next(s for s in bundle.settlements if not s.is_orphan)
            return to_decimal(settlement.actual_settlement)
        primary_payment = next((p for p in bundle.payments if not p.is_orphan), None)
        return to_decimal(primary_payment.amount) if primary_payment else Decimal("0.00")

    if exception_type == "settlement_timing_anomaly":
        primary_settlement = next((s for s in bundle.settlements if not s.is_orphan), None)
        if primary_settlement is not None:
            return to_decimal(primary_settlement.actual_settlement)
        primary_payment = next((p for p in bundle.payments if not p.is_orphan), None)
        return to_decimal(primary_payment.amount) if primary_payment else Decimal("0.00")

    return Decimal("0.00")
