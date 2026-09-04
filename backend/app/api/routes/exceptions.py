"""Exception listing, filtering, and detail endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import ExceptionDetailSchema, ExceptionListItemSchema
from app.core.database import get_db
from app.models.exception import ExceptionRecord, Investigation

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


@router.get("", response_model=List[ExceptionListItemSchema])
def list_exceptions(
    exception_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_exposure: Optional[float] = Query(None),
    max_exposure: Optional[float] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[ExceptionListItemSchema]:
    """List exceptions with optional filters."""

    stmt = select(ExceptionRecord).order_by(ExceptionRecord.detected_at.desc())

    if exception_type:
        stmt = stmt.where(ExceptionRecord.exception_type == exception_type)
    if severity:
        stmt = stmt.where(ExceptionRecord.severity == severity)
    if status:
        stmt = stmt.where(ExceptionRecord.status == status)
    if min_exposure is not None:
        stmt = stmt.where(ExceptionRecord.financial_exposure >= min_exposure)
    if max_exposure is not None:
        stmt = stmt.where(ExceptionRecord.financial_exposure <= max_exposure)

    stmt = stmt.offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()

    return [
        ExceptionListItemSchema(
            exception_id=r.exception_id,
            transaction_id=r.transaction_id,
            exception_type=r.exception_type,
            severity=r.severity,
            financial_exposure=format(r.financial_exposure, "f"),
            status=r.status,
            detected_at=r.detected_at,
            ground_truth_type=r.ground_truth_type,
        )
        for r in rows
    ]


@router.get("/{exception_id}", response_model=ExceptionDetailSchema)
def get_exception(
    exception_id: str,
    db: Session = Depends(get_db),
) -> ExceptionDetailSchema:
    """Return full details for one exception including its investigations."""

    row = db.execute(
        select(ExceptionRecord)
        .options(selectinload(ExceptionRecord.investigations))
        .where(ExceptionRecord.exception_id == exception_id)
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found.")

    from app.api.schemas import InvestigationSchema

    investigations = [
        InvestigationSchema(
            investigation_id=inv.investigation_id,
            exception_id=inv.exception_id,
            transaction_id=inv.transaction_id,
            agent_provider=inv.agent_provider,
            root_cause=inv.root_cause,
            explanation=inv.explanation,
            recommended_action=inv.recommended_action,
            confidence=inv.confidence,
            evidence=inv.evidence,
            created_at=inv.created_at,
        )
        for inv in row.investigations
    ]

    return ExceptionDetailSchema(
        exception_id=row.exception_id,
        transaction_id=row.transaction_id,
        exception_type=row.exception_type,
        severity=row.severity,
        financial_exposure=format(row.financial_exposure, "f"),
        status=row.status,
        detected_at=row.detected_at,
        control_evidence=row.control_evidence,
        ground_truth_type=row.ground_truth_type,
        investigations=investigations,
    )
