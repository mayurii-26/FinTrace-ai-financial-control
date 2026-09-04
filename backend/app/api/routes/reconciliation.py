"""Reconciliation / control execution endpoints."""
from __future__ import annotations

import time
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.anomaly.classifier import classify_exception
from app.anomaly.severity import classify_severity
from app.api.schemas import (
    ReconciliationRequestSchema,
    ReconciliationResponseSchema,
    ReconciliationResultItemSchema,
)
from app.audit.logger import log_action
from app.core.database import get_db
from app.finance.control_engine import run_controls
from app.finance.exposure import compute_financial_exposure
from app.finance.lifecycle_builder import build_bundle
from app.models.exception import ExceptionRecord
from app.models.transaction import Transaction, TransactionStatus

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


def _run_single(db: Session, txn: Transaction) -> ReconciliationResultItemSchema:
    """Run control checks for one transaction and persist the result."""
    bundle = build_bundle(txn)
    control = run_controls(bundle)
    exception_type = classify_exception(control)
    exposure = compute_financial_exposure(bundle, control, exception_type)

    exception_id: Optional[str] = None

    if exception_type:
        txn.status = TransactionStatus.EXCEPTION
        txn.exception_type = exception_type
        txn.financial_exposure = exposure

        severity = classify_severity(exception_type, exposure)
        exc = ExceptionRecord(
            transaction_id=txn.transaction_id,
            exception_type=exception_type,
            severity=severity,
            financial_exposure=exposure,
            control_evidence=control.evidence(),
            ground_truth_type=txn.ground_truth_type,
        )
        db.add(exc)
        db.flush()
        exception_id = exc.exception_id

        log_action(
            db,
            action="reconciliation_exception",
            transaction_id=txn.transaction_id,
            exception_id=exception_id,
            message=f"{exception_type} | exposure={exposure}",
        )
    else:
        txn.status = TransactionStatus.HEALTHY
        txn.exception_type = None
        txn.financial_exposure = Decimal("0.00")
        log_action(
            db,
            action="reconciliation_healthy",
            transaction_id=txn.transaction_id,
            message="All controls passed.",
        )

    return ReconciliationResultItemSchema(
        transaction_id=txn.transaction_id,
        status=txn.status,
        exception_type=exception_type,
        financial_exposure=format(exposure, "f"),
        exception_id=exception_id,
    )


@router.post("", response_model=ReconciliationResponseSchema)
def run_reconciliation(
    body: ReconciliationRequestSchema,
    db: Session = Depends(get_db),
) -> ReconciliationResponseSchema:
    """Run the deterministic control engine.

    - If ``transaction_ids`` is provided, re-run only those transactions.
    - Otherwise, run on all PENDING transactions (or all if force_rerun=True).
    """
    t_start = time.perf_counter()

    if body.transaction_ids:
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.order),
                selectinload(Transaction.payments),
                selectinload(Transaction.refunds),
                selectinload(Transaction.settlements),
                selectinload(Transaction.bank_entries),
            )
            .where(Transaction.transaction_id.in_(body.transaction_ids))
        )
    elif body.force_rerun:
        stmt = select(Transaction).options(
            selectinload(Transaction.order),
            selectinload(Transaction.payments),
            selectinload(Transaction.refunds),
            selectinload(Transaction.settlements),
            selectinload(Transaction.bank_entries),
        )
    else:
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.order),
                selectinload(Transaction.payments),
                selectinload(Transaction.refunds),
                selectinload(Transaction.settlements),
                selectinload(Transaction.bank_entries),
            )
            .where(Transaction.status == TransactionStatus.PENDING)
        )

    transactions = list(db.execute(stmt).scalars().all())
    results: List[ReconciliationResultItemSchema] = []
    healthy = 0
    exceptions_raised = 0

    for txn in transactions:
        item = _run_single(db, txn)
        results.append(item)
        if item.exception_type:
            exceptions_raised += 1
        else:
            healthy += 1

    db.commit()
    duration = time.perf_counter() - t_start

    return ReconciliationResponseSchema(
        processed=len(transactions),
        healthy=healthy,
        exceptions_raised=exceptions_raised,
        results=results,
        duration_seconds=round(duration, 4),
    )
