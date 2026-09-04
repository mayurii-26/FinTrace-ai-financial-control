"""Append-only audit logging helpers.

Every meaningful action taken by the system (data generation, control
evaluation, exception creation/auto-resolution, AI investigation) is
recorded here so the full history of a transaction can be replayed via
``GET /api/audit/{transaction_id}``.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(
    db: Session,
    action: str,
    *,
    transaction_id: Optional[str] = None,
    exception_id: Optional[str] = None,
    actor: str = "system",
    details: Optional[dict] = None,
    message: str = "",
    flush: bool = False,
) -> AuditLog:
    """Create (and add-to-session) one audit log row.

    Does not commit by default - callers running a batch pipeline should
    commit once at the end for performance; API routes handling a single
    action may pass ``flush=True`` to make the row immediately queryable
    within the same transaction.
    """
    entry = AuditLog(
        transaction_id=transaction_id,
        exception_id=exception_id,
        action=action,
        actor=actor,
        details=details or {},
        message=message,
    )
    db.add(entry)
    if flush:
        db.flush()
    return entry
