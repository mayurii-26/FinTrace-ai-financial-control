"""The normalized Financial Lifecycle representation.

Every transaction in FinTrace is reduced to this single, flat structure
before any control check runs. It is the canonical shape referenced by the
hero "Financial Lifecycle Trace" feature: Order -> Payment -> Refund ->
Fees/Tax -> Settlement -> Bank Credit.

All monetary fields are ``Decimal`` and are serialized safely to JSON as
strings by Pydantic v2 (see ``model_config``) so no precision is lost on
the wire.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class TransactionLifecycle(BaseModel):
    """Flat, normalized view of one transaction's financial journey."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str

    order_amount: Decimal = Decimal("0.00")
    payment_amount: Decimal = Decimal("0.00")
    refund_amount: Decimal = Decimal("0.00")
    fee_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    expected_settlement: Decimal = Decimal("0.00")
    actual_settlement: Decimal = Decimal("0.00")
    bank_credit: Decimal = Decimal("0.00")

    payment_timestamp: Optional[datetime] = None
    settlement_timestamp: Optional[datetime] = None
    bank_timestamp: Optional[datetime] = None

    status: str = "pending"
    exception_type: Optional[str] = None
    financial_exposure: Decimal = Decimal("0.00")

    # Present-stage flags (used by the completeness control check).
    has_order: bool = False
    has_payment: bool = False
    has_refund: bool = False
    has_settlement: bool = False
    has_bank_entry: bool = False

    @field_serializer(
        "order_amount",
        "payment_amount",
        "refund_amount",
        "fee_amount",
        "tax_amount",
        "expected_settlement",
        "actual_settlement",
        "bank_credit",
        "financial_exposure",
    )
    def _serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")
