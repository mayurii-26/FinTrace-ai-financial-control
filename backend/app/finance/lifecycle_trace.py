"""Financial lifecycle trace builder.

Constructs a LifecycleTrace with per-stage statuses
(VALID / WARNING / BREAK / MISSING) for the canonical lifecycle:

    ORDER → PAYMENT → REFUND → FEE/TAX → EXPECTED_SETTLEMENT
    → ACTUAL_SETTLEMENT → BANK_CREDIT

Status derivation logic is deterministic and based solely on values
already computed by the control engine (stored in ExceptionRecord.
control_evidence and the Transaction/lifecycle rows).  No monetary
calculations are performed here.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.schemas import LifecycleStage, LifecycleTrace, StageStatus

logger = logging.getLogger(__name__)

# Tolerance for "are two amounts equal enough?"
_AMOUNT_TOLERANCE = Decimal("0.01")


def _stage(
    stage: str,
    status: StageStatus,
    amount: Optional[Any] = None,
    timestamp: Optional[datetime] = None,
    notes: Optional[str] = None,
    raw_ids: Optional[List[str]] = None,
) -> LifecycleStage:
    return LifecycleStage(
        stage=stage,
        status=status,
        amount=_fmt(amount),
        timestamp=timestamp,
        notes=notes,
        raw_ids=raw_ids or [],
    )


def _fmt(v: Any) -> Optional[str]:
    if v is None:
        return None
    return format(v, "f") if isinstance(v, Decimal) else str(v)


def _worst(statuses: List[StageStatus]) -> StageStatus:
    order = [StageStatus.VALID, StageStatus.WARNING, StageStatus.BREAK, StageStatus.MISSING]
    best_idx = 0
    for s in statuses:
        idx = order.index(s) if s in order else 0
        if idx > best_idx:
            best_idx = idx
    return order[best_idx]


def build_lifecycle_trace(db: Session, transaction_id: str) -> LifecycleTrace:
    """Build a complete financial lifecycle trace from actual DB data."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.transaction import Transaction
    from app.models.exception import ExceptionRecord

    txn = db.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.order),
            selectinload(Transaction.payments),
            selectinload(Transaction.refunds),
            selectinload(Transaction.settlements),
            selectinload(Transaction.bank_entries),
        )
        .where(Transaction.transaction_id == transaction_id)
    ).scalar_one_or_none()

    if txn is None:
        return LifecycleTrace(
            transaction_id=transaction_id,
            stages=[],
            overall_status=StageStatus.MISSING,
            exception_type=None,
            financial_exposure="0.00",
        )

    # Load control evidence from the most recent exception record
    exc_record = db.execute(
        select(ExceptionRecord)
        .where(ExceptionRecord.transaction_id == transaction_id)
        .order_by(ExceptionRecord.detected_at.desc())
    ).scalar_one_or_none()

    ctrl = exc_record.control_evidence if exc_record else {}
    exception_type = txn.exception_type
    exposure = txn.financial_exposure or Decimal("0.00")

    stages: List[LifecycleStage] = []

    # ── ORDER ────────────────────────────────────────────────────────────────
    if txn.order:
        stages.append(_stage(
            "ORDER",
            StageStatus.VALID,
            txn.order.amount,
            txn.order.created_at,
            notes="Order created.",
            raw_ids=[txn.order.order_id],
        ))
    else:
        stages.append(_stage("ORDER", StageStatus.MISSING, notes="No order record found."))

    # ── PAYMENT ──────────────────────────────────────────────────────────────
    payments = list(txn.payments or [])
    non_orphan_pays = [p for p in payments if not p.is_orphan]
    orphan_pays = [p for p in payments if p.is_orphan]

    if not payments:
        stages.append(_stage("PAYMENT", StageStatus.MISSING, notes="No payment records found."))
    elif ctrl.get("duplicate_detected"):
        dup_details = ctrl.get("duplicate_details", [])
        stages.append(_stage(
            "PAYMENT",
            StageStatus.BREAK,
            amount=sum((Decimal(str(p.amount)) for p in payments), Decimal("0")),
            timestamp=non_orphan_pays[0].payment_timestamp if non_orphan_pays else None,
            notes=f"Duplicate payment detected. {len(payments)} payment records. Details: {dup_details}",
            raw_ids=[p.payment_id for p in payments],
        ))
    elif orphan_pays:
        stages.append(_stage(
            "PAYMENT",
            StageStatus.BREAK,
            amount=non_orphan_pays[0].amount if non_orphan_pays else None,
            timestamp=non_orphan_pays[0].payment_timestamp if non_orphan_pays else None,
            notes=f"{len(orphan_pays)} orphan payment(s) detected: {[p.payment_id for p in orphan_pays]}",
            raw_ids=[p.payment_id for p in payments],
        ))
    else:
        primary = non_orphan_pays[0]
        amount_diff = ctrl.get("amount_integrity_diff")
        if amount_diff and Decimal(str(amount_diff)) > _AMOUNT_TOLERANCE:
            stages.append(_stage(
                "PAYMENT",
                StageStatus.WARNING,
                primary.amount,
                primary.payment_timestamp,
                notes=f"Amount differs from order by ₹{amount_diff}.",
                raw_ids=[primary.payment_id],
            ))
        else:
            stages.append(_stage(
                "PAYMENT",
                StageStatus.VALID,
                primary.amount,
                primary.payment_timestamp,
                notes="Payment captured, amount matches order.",
                raw_ids=[primary.payment_id],
            ))

    # ── REFUND ───────────────────────────────────────────────────────────────
    refunds = list(txn.refunds or [])
    if refunds:
        total_refund = sum((Decimal(str(r.amount)) for r in refunds), Decimal("0"))
        refund_ok = ctrl.get("refund_consistency_ok", True)
        status = StageStatus.VALID if refund_ok else StageStatus.BREAK
        notes = (
            "Refund processed and reflected in settlement."
            if refund_ok
            else f"Refund of ₹{total_refund} issued but settlement was not adjusted (refund_closure_failure)."
        )
        stages.append(_stage(
            "REFUND",
            status,
            total_refund,
            refunds[-1].refund_timestamp,
            notes=notes,
            raw_ids=[r.refund_id for r in refunds],
        ))
    # No refund stage added if no refunds — refunds are optional

    # ── FEE / TAX ────────────────────────────────────────────────────────────
    settlements = list(txn.settlements or [])
    non_orphan_sets = [s for s in settlements if not s.is_orphan]
    orphan_sets = [s for s in settlements if s.is_orphan]

    if non_orphan_sets:
        s = non_orphan_sets[0]
        fee_total = Decimal(str(s.fee_amount)) + Decimal(str(s.tax_amount))
        stages.append(_stage(
            "FEE_AND_TAX",
            StageStatus.VALID,
            fee_total,
            s.settlement_timestamp,
            notes=f"Fee=₹{_fmt(s.fee_amount)}, GST=₹{_fmt(s.tax_amount)} deducted.",
            raw_ids=[s.settlement_id],
        ))
    elif "settlement" in ctrl.get("missing_stages", []):
        stages.append(_stage("FEE_AND_TAX", StageStatus.MISSING, notes="Settlement record absent; fee/tax not computed."))

    # ── EXPECTED SETTLEMENT ──────────────────────────────────────────────────
    if non_orphan_sets:
        s = non_orphan_sets[0]
        stages.append(_stage(
            "EXPECTED_SETTLEMENT",
            StageStatus.VALID,
            s.expected_settlement,
            s.settlement_timestamp,
            notes="Expected settlement computed by control engine.",
            raw_ids=[s.settlement_id],
        ))
    elif "settlement" in ctrl.get("missing_stages", []):
        stages.append(_stage("EXPECTED_SETTLEMENT", StageStatus.MISSING, notes="No settlement record."))

    # ── ACTUAL SETTLEMENT ────────────────────────────────────────────────────
    if non_orphan_sets:
        s = non_orphan_sets[0]
        consistency_ok = ctrl.get("settlement_consistency_ok", True)
        timing_ok = ctrl.get("settlement_timing_ok", True)
        settle_days_late = ctrl.get("settlement_days_late", 0)
        diff = ctrl.get("settlement_consistency_diff", "0.00")

        if not consistency_ok:
            status = StageStatus.BREAK
            notes = (
                f"Settlement amount ₹{_fmt(s.actual_settlement)} deviates from expected "
                f"₹{_fmt(s.expected_settlement)} by ₹{diff}."
            )
        elif not timing_ok:
            status = StageStatus.WARNING
            notes = f"Settlement arrived {settle_days_late}d late (SLA: 3 days)."
        else:
            status = StageStatus.VALID
            notes = "Settlement amount matches expected. Timing within SLA."

        stages.append(_stage(
            "ACTUAL_SETTLEMENT",
            status,
            s.actual_settlement,
            s.settlement_timestamp,
            notes=notes,
            raw_ids=[s.settlement_id],
        ))
    elif orphan_sets:
        stages.append(_stage(
            "ACTUAL_SETTLEMENT",
            StageStatus.BREAK,
            notes=f"{len(orphan_sets)} orphan settlement(s) with no matching payment.",
            raw_ids=[s.settlement_id for s in orphan_sets],
        ))
    elif "settlement" in ctrl.get("missing_stages", []):
        stages.append(_stage("ACTUAL_SETTLEMENT", StageStatus.MISSING, notes="Settlement never received."))

    # ── BANK CREDIT ──────────────────────────────────────────────────────────
    bank_entries = list(txn.bank_entries or [])
    non_orphan_banks = [b for b in bank_entries if not b.is_orphan]
    orphan_banks = [b for b in bank_entries if b.is_orphan]
    bank_days_late = ctrl.get("bank_days_late", 0)
    bank_sla_ok = ctrl.get("settlement_timing_ok", True)  # timing covers bank too

    if non_orphan_banks:
        b = non_orphan_banks[0]
        if orphan_banks:
            status = StageStatus.BREAK
            notes = f"Orphan bank entries detected: {[b.bank_entry_id for b in orphan_banks]}."
        elif bank_days_late > 2:
            status = StageStatus.WARNING
            notes = f"Bank credit arrived {bank_days_late}d late (SLA: 2 days)."
        else:
            status = StageStatus.VALID
            notes = "Bank credit received within SLA."
        stages.append(_stage(
            "BANK_CREDIT",
            status,
            b.amount,
            b.bank_timestamp,
            notes=notes,
            raw_ids=[b.bank_entry_id for b in bank_entries],
        ))
    elif "bank_entry" in ctrl.get("missing_stages", []):
        stages.append(_stage("BANK_CREDIT", StageStatus.MISSING, notes="Bank credit never received."))

    overall = _worst([s.status for s in stages])

    return LifecycleTrace(
        transaction_id=transaction_id,
        stages=stages,
        overall_status=overall,
        exception_type=exception_type,
        financial_exposure=_fmt(exposure) or "0.00",
    )
