"""Controller action route: POST /api/exceptions/{exception_id}/action

Actions: approve, reject, escalate.

Approval applies a synthetic state transition only.
No real money ever moves through this endpoint.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.schemas import ControllerActionRequest, ControllerActionResponse, ControllerActionType
from app.audit.logger import log_action
from app.core.database import get_db
from app.models.exception import ExceptionRecord, ExceptionStatus

router = APIRouter(tags=["controller"])

# Map action → new status
_ACTION_STATUS_MAP = {
    ControllerActionType.APPROVE: ExceptionStatus.APPROVED,
    ControllerActionType.REJECT: ExceptionStatus.REJECTED,
    ControllerActionType.ESCALATE: ExceptionStatus.ESCALATED,
}

# States that allow a controller action
_ACTIONABLE_STATUSES = {ExceptionStatus.OPEN, ExceptionStatus.AUTO_RESOLVED}


@router.post("/exceptions/{exception_id}/action", response_model=ControllerActionResponse)
def controller_action(
    exception_id: str,
    body: ControllerActionRequest,
    db: Session = Depends(get_db),
) -> ControllerActionResponse:
    """Apply a controller action (approve / reject / escalate) to an exception.

    This is a synthetic state transition only.
    No financial amounts are modified, no real money moves.
    """
    from sqlalchemy import select

    exc = db.execute(
        select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
    ).scalar_one_or_none()

    if exc is None:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found.")

    if exc.status not in _ACTIONABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Exception {exception_id} is in status '{exc.status}' "
                f"and cannot be actioned. Only open/auto_resolved exceptions can be actioned."
            ),
        )

    previous_status = exc.status
    new_status = _ACTION_STATUS_MAP[body.action]
    actioned_at = datetime.utcnow()

    # Apply state transition
    exc.status = new_status
    exc.actioned_by = body.actor
    exc.actioned_at = actioned_at
    exc.action_notes = body.notes

    log_action(
        db,
        action=f"controller_{body.action}",
        transaction_id=exc.transaction_id,
        exception_id=exception_id,
        actor=body.actor,
        details={
            "previous_status": previous_status,
            "new_status": new_status,
            "notes": body.notes,
        },
        message=(
            f"Controller action '{body.action}' applied by '{body.actor}'. "
            f"{previous_status} → {new_status}."
            + (f" Notes: {body.notes}" if body.notes else "")
        ),
        flush=True,
    )

    db.commit()

    return ControllerActionResponse(
        exception_id=exception_id,
        action=body.action,
        previous_status=previous_status,
        new_status=new_status,
        actor=body.actor,
        notes=body.notes,
        actioned_at=actioned_at,
    )
