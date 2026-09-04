"""Builds the normalized ``TransactionLifecycle`` (and the raw per-stage
event lists needed by the control engine) from ORM rows.

This is a pure, side-effect-free transformation layer: it never talks to
the database itself and never performs a financial decision - it simply
reshapes the raw lifecycle rows into the flat representation the control
engine and the API operate on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.finance.lifecycle import TransactionLifecycle
from app.finance.money import sum_decimals, to_decimal
from app.models.transaction import BankEntry, Payment, Refund, Settlement, Transaction


@dataclass
class LifecycleBundle:
    """Everything the control engine needs for one transaction: the flat
    normalized lifecycle plus the raw (possibly duplicated/orphaned) stage
    rows so duplicate/orphan checks can inspect them individually."""

    transaction: Transaction
    lifecycle: TransactionLifecycle
    payments: List[Payment] = field(default_factory=list)
    refunds: List[Refund] = field(default_factory=list)
    settlements: List[Settlement] = field(default_factory=list)
    bank_entries: List[BankEntry] = field(default_factory=list)


def _primary(items: list, key: str = "payment_timestamp"):
    """Pick the earliest non-orphan row as the 'primary' event for a
    stage, falling back to the earliest row overall if all are orphans."""
    if not items:
        return None
    non_orphan = [i for i in items if not getattr(i, "is_orphan", False)]
    pool = non_orphan or items
    return sorted(pool, key=lambda i: getattr(i, key, None) or 0)[0]


def build_bundle(transaction: Transaction) -> LifecycleBundle:
    """Build a ``LifecycleBundle`` from a fully-loaded ``Transaction`` ORM
    row (its ``order``/``payments``/``refunds``/``settlements``/
    ``bank_entries`` relationships must already be populated)."""

    order = transaction.order
    payments = list(transaction.payments or [])
    refunds = list(transaction.refunds or [])
    settlements = list(transaction.settlements or [])
    bank_entries = list(transaction.bank_entries or [])

    primary_payment: Optional[Payment] = _primary(payments, "payment_timestamp")
    primary_settlement: Optional[Settlement] = _primary(settlements, "settlement_timestamp")
    primary_bank_entry: Optional[BankEntry] = _primary(bank_entries, "bank_timestamp")

    refund_amount = sum_decimals([r.amount for r in refunds])

    lifecycle = TransactionLifecycle(
        transaction_id=transaction.transaction_id,
        order_amount=to_decimal(order.amount) if order else to_decimal(0),
        payment_amount=to_decimal(primary_payment.amount) if primary_payment else to_decimal(0),
        refund_amount=refund_amount,
        fee_amount=to_decimal(primary_settlement.fee_amount) if primary_settlement else to_decimal(0),
        tax_amount=to_decimal(primary_settlement.tax_amount) if primary_settlement else to_decimal(0),
        expected_settlement=to_decimal(primary_settlement.expected_settlement) if primary_settlement else to_decimal(0),
        actual_settlement=to_decimal(primary_settlement.actual_settlement) if primary_settlement else to_decimal(0),
        bank_credit=to_decimal(primary_bank_entry.amount) if primary_bank_entry else to_decimal(0),
        payment_timestamp=primary_payment.payment_timestamp if primary_payment else None,
        settlement_timestamp=primary_settlement.settlement_timestamp if primary_settlement else None,
        bank_timestamp=primary_bank_entry.bank_timestamp if primary_bank_entry else None,
        status=transaction.status,
        exception_type=transaction.exception_type,
        financial_exposure=to_decimal(transaction.financial_exposure),
        has_order=order is not None,
        has_payment=bool(payments) and any(not p.is_orphan for p in payments),
        has_refund=bool(refunds),
        has_settlement=bool(settlements) and any(not s.is_orphan for s in settlements),
        has_bank_entry=bool(bank_entries) and any(not b.is_orphan for b in bank_entries),
    )

    return LifecycleBundle(
        transaction=transaction,
        lifecycle=lifecycle,
        payments=payments,
        refunds=refunds,
        settlements=settlements,
        bank_entries=bank_entries,
    )
