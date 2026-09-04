"""ORM models for detected exceptions and their AI-agent investigations.

The domain model is called ``ExceptionRecord`` in Python code (to avoid
shadowing the built-in ``Exception`` class) but maps to the ``exceptions``
table - no schema change required.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.transaction import Transaction

MONEY = Numeric(18, 2, asdecimal=True)


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionStatus(str, enum.Enum):
    OPEN = "open"
    AUTO_RESOLVED = "auto_resolved"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


def _new_id() -> str:
    return f"EXC-{uuid.uuid4().hex[:12].upper()}"


class ExceptionRecord(Base):
    """A detected control break for a transaction lifecycle.

    The class is named ``ExceptionRecord`` to avoid shadowing Python's
    built-in ``Exception``. The database table is still ``exceptions``.
    """

    __tablename__ = "exceptions"

    exception_id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_new_id)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.transaction_id"))
    exception_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(Enum(Severity, native_enum=False, length=16))
    financial_exposure: Mapped[Decimal] = mapped_column(MONEY)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(
        Enum(ExceptionStatus, native_enum=False, length=16), default=ExceptionStatus.OPEN
    )
    control_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    ground_truth_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Controller action metadata
    actioned_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    action_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    transaction: Mapped["Transaction"] = relationship(back_populates="exceptions")
    investigations: Mapped[List["Investigation"]] = relationship(
        back_populates="exception", cascade="all, delete-orphan"
    )


def _new_investigation_id() -> str:
    return f"INV-{uuid.uuid4().hex[:12].upper()}"


class Investigation(Base):
    """An AI-agent investigation result attached to an exception.

    The ``evidence`` JSON column stores the full structured output including:
    - evidence dict (key facts from tool calls)
    - missing_evidence list
    - impact_summary
    - confidence_band
    - requires_human_review
    - tool_calls (list of ToolCallRecord dicts — only actually-executed calls)
    - lifecycle_trace (serialized LifecycleTrace)
    """

    __tablename__ = "investigations"

    investigation_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=_new_investigation_id
    )
    exception_id: Mapped[str] = mapped_column(ForeignKey("exceptions.exception_id"))
    transaction_id: Mapped[str] = mapped_column(String(40))
    agent_provider: Mapped[str] = mapped_column(String(32))
    root_cause: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)          # stores recommendation text
    recommended_action: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(default=0.0)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)  # full structured output
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    exception: Mapped["ExceptionRecord"] = relationship(back_populates="investigations")


# Backwards-compat alias so old import sites that used ``Exception`` still work.
# Prefer ``ExceptionRecord`` in all new code.
Exception = ExceptionRecord  # noqa: A001
