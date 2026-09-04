"""Read-only investigation tools for the FinTrace AI agent.

Each tool queries actual database records and returns structured data.
Tools are pure functions — they never write to the database and never
perform monetary calculations. All returned amounts are pre-computed
values read from the DB rows.

The agent calls tools by name and accumulates ``ToolCallRecord`` objects
for every tool that was actually executed (not just defined).
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.schemas import ToolCallRecord

logger = logging.getLogger(__name__)

# Sentinel returned when a tool finds nothing
_NOT_FOUND = {"found": False}


# ---------------------------------------------------------------------------
# Decimal serialiser helper
# ---------------------------------------------------------------------------

def _d(v: Any) -> Optional[str]:
    if v is None:
        return None
    return format(v, "f") if isinstance(v, Decimal) else str(v)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_get_transaction(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Fetch core transaction fields (status, type, exposure, ground truth)."""
    from sqlalchemy import select
    from app.models.transaction import Transaction

    txn = db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    ).scalar_one_or_none()

    if txn is None:
        return {**_NOT_FOUND, "transaction_id": transaction_id}

    return {
        "found": True,
        "transaction_id": txn.transaction_id,
        "currency": txn.currency,
        "status": txn.status,
        "exception_type": txn.exception_type,
        "financial_exposure": _d(txn.financial_exposure),
        "ground_truth_type": txn.ground_truth_type,
        "ground_truth_is_anomaly": txn.ground_truth_is_anomaly,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
    }


def tool_get_order(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Fetch the order for a transaction."""
    from sqlalchemy import select
    from app.models.transaction import Order

    order = db.execute(
        select(Order).where(Order.transaction_id == transaction_id)
    ).scalar_one_or_none()

    if order is None:
        return {**_NOT_FOUND, "transaction_id": transaction_id, "stage": "order"}

    return {
        "found": True,
        "order_id": order.order_id,
        "transaction_id": order.transaction_id,
        "amount": _d(order.amount),
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def tool_get_payments(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Fetch all payment records for a transaction (including orphans)."""
    from sqlalchemy import select
    from app.models.transaction import Payment

    payments = db.execute(
        select(Payment)
        .where(Payment.transaction_id == transaction_id)
        .order_by(Payment.payment_timestamp)
    ).scalars().all()

    if not payments:
        return {**_NOT_FOUND, "transaction_id": transaction_id, "stage": "payment"}

    items = [
        {
            "payment_id": p.payment_id,
            "amount": _d(p.amount),
            "status": p.status,
            "is_orphan": p.is_orphan,
            "order_id": p.order_id,
            "timestamp": p.payment_timestamp.isoformat() if p.payment_timestamp else None,
        }
        for p in payments
    ]
    orphan_count = sum(1 for p in payments if p.is_orphan)
    return {
        "found": True,
        "transaction_id": transaction_id,
        "count": len(payments),
        "orphan_count": orphan_count,
        "duplicate_detected": len(payments) > 1 and orphan_count == 0,
        "payments": items,
    }


def tool_get_refunds(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Fetch all refund records for a transaction."""
    from sqlalchemy import select
    from app.models.transaction import Refund

    refunds = db.execute(
        select(Refund)
        .where(Refund.transaction_id == transaction_id)
        .order_by(Refund.refund_timestamp)
    ).scalars().all()

    if not refunds:
        return {
            "found": False,
            "transaction_id": transaction_id,
            "stage": "refund",
            "refund_present": False,
        }

    total_refund = sum(Decimal(str(r.amount)) for r in refunds)
    items = [
        {
            "refund_id": r.refund_id,
            "payment_id": r.payment_id,
            "amount": _d(r.amount),
            "status": r.status,
            "timestamp": r.refund_timestamp.isoformat() if r.refund_timestamp else None,
        }
        for r in refunds
    ]
    return {
        "found": True,
        "transaction_id": transaction_id,
        "refund_present": True,
        "count": len(refunds),
        "total_refund_amount": _d(total_refund),
        "refunds": items,
    }


def tool_get_settlements(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Fetch all settlement records for a transaction."""
    from sqlalchemy import select
    from app.models.transaction import Settlement

    settlements = db.execute(
        select(Settlement)
        .where(Settlement.transaction_id == transaction_id)
        .order_by(Settlement.settlement_timestamp)
    ).scalars().all()

    if not settlements:
        return {**_NOT_FOUND, "transaction_id": transaction_id, "stage": "settlement"}

    items = [
        {
            "settlement_id": s.settlement_id,
            "payment_id": s.payment_id,
            "expected_settlement": _d(s.expected_settlement),
            "actual_settlement": _d(s.actual_settlement),
            "fee_amount": _d(s.fee_amount),
            "tax_amount": _d(s.tax_amount),
            "is_orphan": s.is_orphan,
            "timestamp": s.settlement_timestamp.isoformat() if s.settlement_timestamp else None,
        }
        for s in settlements
    ]
    return {
        "found": True,
        "transaction_id": transaction_id,
        "count": len(settlements),
        "settlements": items,
    }


def tool_get_bank_entries(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Fetch all bank entry records for a transaction."""
    from sqlalchemy import select
    from app.models.transaction import BankEntry

    entries = db.execute(
        select(BankEntry)
        .where(BankEntry.transaction_id == transaction_id)
        .order_by(BankEntry.bank_timestamp)
    ).scalars().all()

    if not entries:
        return {**_NOT_FOUND, "transaction_id": transaction_id, "stage": "bank_entry"}

    items = [
        {
            "bank_entry_id": b.bank_entry_id,
            "settlement_id": b.settlement_id,
            "amount": _d(b.amount),
            "is_orphan": b.is_orphan,
            "timestamp": b.bank_timestamp.isoformat() if b.bank_timestamp else None,
        }
        for b in entries
    ]
    return {
        "found": True,
        "transaction_id": transaction_id,
        "count": len(entries),
        "bank_entries": items,
    }


def tool_get_financial_timeline(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Assemble a chronological financial timeline for a transaction.

    Combines order, payments, refunds, settlements and bank entries into
    a single ordered list. Also computes timing gaps between stages.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.transaction import Transaction

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
        return {**_NOT_FOUND, "transaction_id": transaction_id}

    events = []

    def _add(stage: str, ts: Optional[datetime], amount: Any, extra: Dict = None, is_orphan: bool = False):
        events.append({
            "stage": stage + (" [ORPHAN]" if is_orphan else ""),
            "timestamp": ts.isoformat() if ts else None,
            "amount": _d(amount),
            **(extra or {}),
        })

    if txn.order:
        _add("ORDER", txn.order.created_at, txn.order.amount)

    for p in sorted(txn.payments, key=lambda x: x.payment_timestamp or datetime.min):
        _add("PAYMENT", p.payment_timestamp, p.amount, {"status": p.status}, p.is_orphan)

    for r in sorted(txn.refunds, key=lambda x: x.refund_timestamp or datetime.min):
        _add("REFUND", r.refund_timestamp, r.amount, {"status": r.status})

    for s in sorted(txn.settlements, key=lambda x: x.settlement_timestamp or datetime.min):
        _add(
            "SETTLEMENT",
            s.settlement_timestamp,
            s.actual_settlement,
            {
                "expected": _d(s.expected_settlement),
                "fee": _d(s.fee_amount),
                "tax": _d(s.tax_amount),
                "discrepancy": _d(
                    abs(Decimal(str(s.expected_settlement)) - Decimal(str(s.actual_settlement)))
                ),
            },
            s.is_orphan,
        )

    for b in sorted(txn.bank_entries, key=lambda x: x.bank_timestamp or datetime.min):
        _add("BANK_CREDIT", b.bank_timestamp, b.amount, {}, b.is_orphan)

    # Sort by timestamp (None values go last)
    events.sort(key=lambda e: e.get("timestamp") or "9999")

    # Compute timing gaps between consecutive stages
    gaps = []
    prev_ts = None
    for ev in events:
        ts_str = ev.get("timestamp")
        if ts_str and prev_ts:
            try:
                curr = datetime.fromisoformat(ts_str)
                prev = datetime.fromisoformat(prev_ts)
                gap_hours = round((curr - prev).total_seconds() / 3600, 2)
                gaps.append({"from": prev_ts, "to": ts_str, "gap_hours": gap_hours})
            except Exception:
                pass
        if ts_str:
            prev_ts = ts_str

    return {
        "found": True,
        "transaction_id": transaction_id,
        "event_count": len(events),
        "events": events,
        "timing_gaps": gaps,
    }


def tool_get_control_evidence(db: Session, exception_id: str) -> Dict[str, Any]:
    """Fetch the stored control evidence from the exception record."""
    from sqlalchemy import select
    from app.models.exception import ExceptionRecord

    exc = db.execute(
        select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
    ).scalar_one_or_none()

    if exc is None:
        return {**_NOT_FOUND, "exception_id": exception_id}

    return {
        "found": True,
        "exception_id": exc.exception_id,
        "exception_type": exc.exception_type,
        "severity": exc.severity,
        "financial_exposure": _d(exc.financial_exposure),
        "control_evidence": exc.control_evidence,
        "status": exc.status,
        "detected_at": exc.detected_at.isoformat() if exc.detected_at else None,
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

# Maps tool name → callable(db, **kwargs) → dict
TOOL_REGISTRY: Dict[str, Callable] = {
    "get_transaction": tool_get_transaction,
    "get_order": tool_get_order,
    "get_payments": tool_get_payments,
    "get_refunds": tool_get_refunds,
    "get_settlements": tool_get_settlements,
    "get_bank_entries": tool_get_bank_entries,
    "get_financial_timeline": tool_get_financial_timeline,
    "get_control_evidence": tool_get_control_evidence,
}


def execute_tool(
    db: Session,
    tool_name: str,
    arguments: Dict[str, Any],
) -> tuple[Dict[str, Any], ToolCallRecord]:
    """Execute a named tool and return (result, ToolCallRecord).

    Only tools in TOOL_REGISTRY can be called. Unknown tool names return
    an error dict without a DB call.
    """
    if tool_name not in TOOL_REGISTRY:
        result = {"error": f"Unknown tool: {tool_name}"}
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            result_summary=f"ERROR: unknown tool '{tool_name}'",
        )
        return result, record

    fn = TOOL_REGISTRY[tool_name]
    try:
        result = fn(db, **arguments)
    except Exception as exc:
        logger.exception("Tool %s failed with arguments %s", tool_name, arguments)
        result = {"error": str(exc), "tool": tool_name}
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            result_summary=f"ERROR: {exc}",
        )
        return result, record

    # Build a concise summary for the record
    if result.get("found") is False:
        summary = f"No {tool_name.replace('get_', '')} found for {list(arguments.values())}"
    elif tool_name == "get_payments":
        summary = (
            f"Found {result.get('count', 0)} payment(s); "
            f"orphan_count={result.get('orphan_count', 0)}; "
            f"duplicate={result.get('duplicate_detected', False)}"
        )
    elif tool_name == "get_financial_timeline":
        summary = f"Timeline has {result.get('event_count', 0)} events"
    elif tool_name == "get_settlements":
        count = result.get("count", 0)
        items = result.get("settlements", [])
        if items:
            s = items[0]
            summary = (
                f"{count} settlement(s); expected={s.get('expected_settlement')}; "
                f"actual={s.get('actual_settlement')}"
            )
        else:
            summary = f"{count} settlement(s) found"
    elif tool_name == "get_control_evidence":
        summary = (
            f"exception_type={result.get('exception_type')}; "
            f"exposure={result.get('financial_exposure')}"
        )
    else:
        summary = f"Returned data for {list(arguments.values())}"

    record = ToolCallRecord(
        tool_name=tool_name,
        arguments=arguments,
        result_summary=summary,
    )
    return result, record
