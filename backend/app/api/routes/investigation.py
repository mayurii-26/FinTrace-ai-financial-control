"""AI investigation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.investigator import investigate
from app.api.schemas import (
    InvestigationRequestSchema,
    InvestigationResponseSchema,
    InvestigationSchema,
)
from app.core.database import get_db

router = APIRouter(prefix="/investigation", tags=["investigation"])


@router.post("", response_model=InvestigationResponseSchema)
def run_investigation(
    body: InvestigationRequestSchema,
    db: Session = Depends(get_db),
) -> InvestigationResponseSchema:
    """Trigger an AI investigation for a given exception_id."""

    result = investigate(db, body.exception_id, provider=body.provider)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Exception {body.exception_id} not found.",
        )

    inv = result["investigation"]

    return InvestigationResponseSchema(
        investigation=InvestigationSchema(
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
        ),
        requires_human_review=result["requires_human_review"],
        missing_evidence=result["missing_evidence"],
    )
