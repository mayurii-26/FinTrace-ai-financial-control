"""Seed and transaction lifecycle endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import (
    SeedRequestSchema,
    SeedResponseSchema,
    TransactionLifecycleSchema,
)
from app.core.database import get_db
from app.finance.lifecycle_builder import build_bundle
from app.models.transaction import Transaction

router = APIRouter(tags=["transactions"])


@router.post("/seed", response_model=SeedResponseSchema)
def seed_data(
    body: SeedRequestSchema,
    db: Session = Depends(get_db),
) -> SeedResponseSchema:
    """Generate and persist synthetic transaction data."""
    from app.data.seeder import seed_database

    inserted = seed_database(db, count=body.count, seed=body.seed, force=body.force)
    if inserted == 0 and not body.force:
        return SeedResponseSchema(
            inserted=0,
            message="Database already contains data. Use force=true to re-seed.",
        )
    return SeedResponseSchema(inserted=inserted, message=f"Seeded {inserted} transactions.")


@router.get("/transactions/{transaction_id}/lifecycle", response_model=TransactionLifecycleSchema)
def get_transaction_lifecycle(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> TransactionLifecycleSchema:
    """Return the full normalized financial lifecycle for one transaction."""

    txn = db.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.order),
            selectinload(Transaction.payments),
            selectinload(Transaction.refunds),
            selectinload(Transaction.settlements),
            selectinload(Transaction.bank_entries),
        )
        .where(Transaction.transaction_id == transaction_id)
    ).scalar_one_or_none()

    if txn is None:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found.")

    bundle = build_bundle(txn)
    lc = bundle.lifecycle

    return TransactionLifecycleSchema(
        transaction_id=txn.transaction_id,
        status=txn.status,
        exception_type=txn.exception_type,
        financial_exposure=format(txn.financial_exposure, "f"),
        ground_truth_type=txn.ground_truth_type,
        ground_truth_is_anomaly=txn.ground_truth_is_anomaly,
        order_amount=format(lc.order_amount, "f"),
        payment_amount=format(lc.payment_amount, "f"),
        refund_amount=format(lc.refund_amount, "f"),
        fee_amount=format(lc.fee_amount, "f"),
        tax_amount=format(lc.tax_amount, "f"),
        expected_settlement=format(lc.expected_settlement, "f"),
        actual_settlement=format(lc.actual_settlement, "f"),
        bank_credit=format(lc.bank_credit, "f"),
        payment_timestamp=lc.payment_timestamp,
        settlement_timestamp=lc.settlement_timestamp,
        bank_timestamp=lc.bank_timestamp,
        has_order=lc.has_order,
        has_payment=lc.has_payment,
        has_refund=lc.has_refund,
        has_settlement=lc.has_settlement,
        has_bank_entry=lc.has_bank_entry,
    )
