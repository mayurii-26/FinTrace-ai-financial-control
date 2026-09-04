"""ORM model for the append-only audit trail."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _new_audit_id() -> str:
    return f"AUD-{uuid.uuid4().hex[:12].upper()}"


class AuditLog(Base):
    """Immutable record of every control/agent/system action taken."""

    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_new_audit_id)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    exception_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(32), default="system")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
