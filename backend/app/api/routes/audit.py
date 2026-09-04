"""Audit trail routes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog

router = APIRouter(tags=["audit"])


class AuditLogOut(BaseModel):
    audit_id: str
    transaction_id: Optional[str]
    exception_id: Optional[str]
    action: str
    actor: str
    details: Dict[str, Any]
    message: str
    created_at: datetime


@router.get("/audit/{transaction_id}", response_model=List[AuditLogOut])
def get_audit_trail(
    transaction_id: str,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> List[AuditLogOut]:
    """Return the full audit trail for a transaction."""
    rows = db.execute(
        select(AuditLog)
        .where(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.created_at.asc())
        .limit(limit)
    ).scalars().all()

    return [
        AuditLogOut(
            audit_id=r.audit_id,
            transaction_id=r.transaction_id,
            exception_id=r.exception_id,
            action=r.action,
            actor=r.actor,
            details=r.details,
            message=r.message,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/audit", response_model=List[AuditLogOut])
def get_recent_audit_logs(
    action: Optional[str] = Query(None),
    exception_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> List[AuditLogOut]:
    """Return recent audit logs, optionally filtered by action or exception_id."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if exception_id:
        stmt = stmt.where(AuditLog.exception_id == exception_id)

    rows = db.execute(stmt).scalars().all()
    return [
        AuditLogOut(
            audit_id=r.audit_id,
            transaction_id=r.transaction_id,
            exception_id=r.exception_id,
            action=r.action,
            actor=r.actor,
            details=r.details,
            message=r.message,
            created_at=r.created_at,
        )
        for r in rows
    ]
