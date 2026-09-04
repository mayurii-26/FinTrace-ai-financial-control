"""Verification route: POST /api/exceptions/{exception_id}/verify

Re-runs the deterministic control engine against the current state of the
transaction and returns before/after exposure comparison.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.schemas import VerificationResponse, VerificationStatus
from app.anomaly.classifier import classify_exception
from app.audit.logger import log_action
from app.core.database import get_db
from app.finance.control_engine import run_controls
from app.finance.exposure import compute_financial_exposure
from app.finance.lifecycle_builder import build_bundle
from app.models.exception import ExceptionRecord
from app.models.transaction import Transaction

router = APIRouter(tags=["verification"])


@router.post("/exceptions/{exception_id}/verify", response_model=VerificationResponse)
def verify_exception(
    exception_id: str,
    db: Session = Depends(get_db),
) -> VerificationResponse:
    """Re-run deterministic control for an exception's transaction.

    Returns before_exposure (stored on the exception), after_exposure
    (freshly computed), and a verification_status:
      - resolved:  after_exception_type is None (no longer an anomaly)
      - improved:  after_exposure < before_exposure but still anomalous
      - persists:  same or worse condition
    """
    exc = db.execute(
        select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
    ).scalar_one_or_none()

    if exc is None:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found.")

    # Load the transaction with full relationships
    txn = db.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.order),
            selectinload(Transaction.payments),
            selectinload(Transaction.refunds),
            selectinload(Transaction.settlements),
            selectinload(Transaction.bank_entries),
        )
        .where(Transaction.transaction_id == exc.transaction_id)
    ).scalar_one_or_none()

    if txn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction {exc.transaction_id} not found.",
        )

    before_type = exc.exception_type
    before_exposure = exc.financial_exposure

    # Re-run deterministic control engine
    bundle = build_bundle(txn)
    control = run_controls(bundle)
    after_type = classify_exception(control)
    after_exposure = compute_financial_exposure(bundle, control, after_type)

    # Determine verification status
    if after_type is None:
        verification_status = VerificationStatus.RESOLVED
    elif after_exposure < before_exposure:
        verification_status = VerificationStatus.IMPROVED
    else:
        verification_status = VerificationStatus.PERSISTS

    verified_at = datetime.utcnow()

    log_action(
        db,
        action="verification_run",
        transaction_id=exc.transaction_id,
        exception_id=exception_id,
        actor="system",
        details={
            "before_exception_type": before_type,
            "after_exception_type": after_type,
            "before_exposure": format(before_exposure, "f"),
            "after_exposure": format(after_exposure, "f"),
            "verification_status": verification_status,
            "control_result": control.evidence(),
        },
        message=(
            f"Verification: {before_type} → {after_type or 'resolved'}. "
            f"Exposure: ₹{before_exposure} → ₹{after_exposure}. "
            f"Status: {verification_status}."
        ),
        flush=True,
    )
    db.commit()

    return VerificationResponse(
        exception_id=exception_id,
        transaction_id=exc.transaction_id,
        before_exception_type=before_type,
        after_exception_type=after_type,
        before_exposure=format(before_exposure, "f"),
        after_exposure=format(after_exposure, "f"),
        verification_status=verification_status,
        control_result_summary=control.evidence(),
        verified_at=verified_at,
    )
