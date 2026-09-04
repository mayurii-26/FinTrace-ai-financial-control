"""Investigation route: POST /api/exceptions/{exception_id}/investigate

Replaces the old /api/investigation endpoint.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.agent import run_investigation
from app.core.database import get_db

router = APIRouter(tags=["investigation"])


class InvestigateRequest(BaseModel):
    provider: str = "mock"  # "mock" | "openai"


class ToolCallOut(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result_summary: str


class LifecycleStageOut(BaseModel):
    stage: str
    status: str
    amount: Optional[str] = None
    timestamp: Optional[str] = None
    notes: Optional[str] = None
    raw_ids: List[str] = []


class LifecycleTraceOut(BaseModel):
    transaction_id: str
    stages: List[LifecycleStageOut]
    overall_status: str
    exception_type: Optional[str] = None
    financial_exposure: str


class InvestigationOut(BaseModel):
    investigation_id: str
    exception_id: str
    transaction_id: str
    agent_provider: str
    root_cause: str
    explanation: str
    recommended_action: str
    confidence: float
    confidence_band: str
    impact_summary: str
    requires_human_review: bool
    missing_evidence: List[str]
    tool_calls: List[ToolCallOut]
    lifecycle_trace: Optional[LifecycleTraceOut] = None
    financial_exposure: str
    created_at: str


class InvestigateResponse(BaseModel):
    investigation: InvestigationOut
    requires_human_review: bool
    missing_evidence: List[str]
    lifecycle_trace: Optional[LifecycleTraceOut] = None


@router.post("/exceptions/{exception_id}/investigate", response_model=InvestigateResponse)
def investigate_exception(
    exception_id: str,
    body: InvestigateRequest,
    db: Session = Depends(get_db),
) -> InvestigateResponse:
    """Run an AI investigation for the given exception.

    The agent reads actual DB evidence via read-only tools, produces a
    structured root-cause finding, and persists the result with a full
    audit trail.
    """
    result = run_investigation(db, exception_id, provider_name=body.provider)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found.")

    inv = result["investigation"]
    output = result["output"]

    # Serialize tool_calls from the output (only actually-executed calls)
    tool_calls_out = [
        ToolCallOut(
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            result_summary=tc.result_summary,
        )
        for tc in output.tool_calls
    ]

    # Serialize lifecycle trace
    trace_out: Optional[LifecycleTraceOut] = None
    if output.lifecycle_trace:
        lt = output.lifecycle_trace
        trace_out = LifecycleTraceOut(
            transaction_id=lt.transaction_id,
            stages=[
                LifecycleStageOut(
                    stage=s.stage,
                    status=s.status,
                    amount=s.amount,
                    timestamp=s.timestamp.isoformat() if s.timestamp else None,
                    notes=s.notes,
                    raw_ids=s.raw_ids,
                )
                for s in lt.stages
            ],
            overall_status=lt.overall_status,
            exception_type=lt.exception_type,
            financial_exposure=lt.financial_exposure,
        )

    # Pull metadata stored in evidence JSON
    ev_dict = inv.evidence or {}
    confidence_band = ev_dict.get("confidence_band", "unknown")
    impact_summary = ev_dict.get("impact_summary", "")
    requires_human = ev_dict.get("requires_human_review", True)
    missing_ev = ev_dict.get("missing_evidence", [])
    raw_tool_calls = ev_dict.get("tool_calls", [])

    inv_out = InvestigationOut(
        investigation_id=inv.investigation_id,
        exception_id=inv.exception_id,
        transaction_id=inv.transaction_id,
        agent_provider=inv.agent_provider,
        root_cause=inv.root_cause,
        explanation=inv.explanation,
        recommended_action=inv.recommended_action,
        confidence=inv.confidence,
        confidence_band=confidence_band,
        impact_summary=impact_summary,
        requires_human_review=requires_human,
        missing_evidence=missing_ev,
        tool_calls=tool_calls_out,
        lifecycle_trace=trace_out,
        financial_exposure=output.financial_exposure,
        created_at=inv.created_at.isoformat() if inv.created_at else "",
    )

    return InvestigateResponse(
        investigation=inv_out,
        requires_human_review=requires_human,
        missing_evidence=missing_ev,
        lifecycle_trace=trace_out,
    )
