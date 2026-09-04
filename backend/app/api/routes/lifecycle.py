"""Lifecycle trace route: GET /api/transactions/{transaction_id}/trace"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.finance.lifecycle_trace import build_lifecycle_trace

router = APIRouter(tags=["lifecycle"])


class StageOut(BaseModel):
    stage: str
    status: str
    amount: Optional[str] = None
    timestamp: Optional[str] = None
    notes: Optional[str] = None
    raw_ids: List[str] = []


class LifecycleTraceResponse(BaseModel):
    transaction_id: str
    stages: List[StageOut]
    overall_status: str
    exception_type: Optional[str] = None
    financial_exposure: str
    traced_at: str


@router.get("/transactions/{transaction_id}/trace", response_model=LifecycleTraceResponse)
def get_lifecycle_trace(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> LifecycleTraceResponse:
    """Return a financial lifecycle trace with per-stage statuses.

    Each stage has a status of VALID, WARNING, BREAK, or MISSING based
    on actual data from the deterministic control engine.
    """
    trace = build_lifecycle_trace(db, transaction_id)

    if not trace.stages:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found.")

    return LifecycleTraceResponse(
        transaction_id=trace.transaction_id,
        stages=[
            StageOut(
                stage=s.stage,
                status=s.status,
                amount=s.amount,
                timestamp=s.timestamp.isoformat() if s.timestamp else None,
                notes=s.notes,
                raw_ids=s.raw_ids,
            )
            for s in trace.stages
        ],
        overall_status=trace.overall_status,
        exception_type=trace.exception_type,
        financial_exposure=trace.financial_exposure,
        traced_at=trace.traced_at.isoformat(),
    )
