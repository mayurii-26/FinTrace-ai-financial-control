"""Core lifecycle ORM models: Transaction -> Order -> Payment -> Refund ->
Settlement -> BankEntry.

These tables represent the raw, per-stage financial events that make up a
transaction's lifecycle. The ``Transaction`` row is the anchor entity and
carries the *outcome* of the control engine (status / exception_type /
financial_exposure) once a reconciliation run has evaluated it.
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

MONEY = Numeric(18, 2, asdecimal=True)


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    HEALTHY = "healthy"
    EXCEPTION = "exception"


class Transaction(Base):
    """Anchor entity for one end-to-end financial lifecycle."""

    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    # Ground truth (used exclusively for benchmark evaluation - never used
    # by the control engine or the AI agent to make decisions).
    ground_truth_type: Mapped[str] = mapped_column(String(64), default="healthy")
    ground_truth_is_anomaly: Mapped[bool] = mapped_column(default=False)

    # Outcome of the deterministic control engine + anomaly classifier.
    status: Mapped[str] = mapped_column(
        Enum(TransactionStatus, native_enum=False, length=32),
        default=TransactionStatus.PENDING,
    )
    exception_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    financial_exposure: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    order: Mapped[Optional["Order"]] = relationship(
        back_populates="transaction", uselist=False, cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    refunds: Mapped[List["Refund"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    settlements: Mapped[List["Settlement"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    bank_entries: Mapped[List["BankEntry"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    exceptions: Mapped[List["ExceptionRecord"]] = relationship(  # noqa: F821
        back_populates="transaction", cascade="all, delete-orphan"
    )


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"), unique=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    transaction: Mapped["Transaction"] = relationship(back_populates="order")


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"))
    order_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(24), default="captured")
    payment_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_orphan: Mapped[bool] = mapped_column(default=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="payments")


class Refund(Base):
    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"))
    payment_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(24), default="processed")
    refund_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    transaction: Mapped["Transaction"] = relationship(back_populates="refunds")


class Settlement(Base):
    __tablename__ = "settlements"

    settlement_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"))
    payment_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    fee_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    expected_settlement: Mapped[Decimal] = mapped_column(MONEY)
    actual_settlement: Mapped[Decimal] = mapped_column(MONEY)
    settlement_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_orphan: Mapped[bool] = mapped_column(default=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="settlements")


class BankEntry(Base):
    __tablename__ = "bank_entries"

    bank_entry_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"))
    settlement_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    bank_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_orphan: Mapped[bool] = mapped_column(default=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="bank_entries")
