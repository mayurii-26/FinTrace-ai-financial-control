"""Dashboard KPI endpoints."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import DashboardKPISchema
from app.core.database import get_db
from app.models.exception import ExceptionRecord, ExceptionStatus
from app.models.transaction import Transaction, TransactionStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardKPISchema)
def get_dashboard_kpis(db: Session = Depends(get_db)) -> DashboardKPISchema:
    """Return high-level KPIs for the FinTrace dashboard."""

    # Transaction counts
    total = db.execute(select(func.count(Transaction.transaction_id))).scalar() or 0
    healthy = (
        db.execute(
            select(func.count(Transaction.transaction_id)).where(
                Transaction.status == TransactionStatus.HEALTHY
            )
        ).scalar()
        or 0
    )
    exception_count = (
        db.execute(
            select(func.count(Transaction.transaction_id)).where(
                Transaction.status == TransactionStatus.EXCEPTION
            )
        ).scalar()
        or 0
    )

    # Exception status breakdown
    open_exc = (
        db.execute(
            select(func.count(ExceptionRecord.exception_id)).where(
                ExceptionRecord.status == ExceptionStatus.OPEN
            )
        ).scalar()
        or 0
    )
    auto_resolved = (
        db.execute(
            select(func.count(ExceptionRecord.exception_id)).where(
                ExceptionRecord.status == ExceptionStatus.AUTO_RESOLVED
            )
        ).scalar()
        or 0
    )

    # Total financial exposure
    total_exposure_raw = (
        db.execute(select(func.sum(ExceptionRecord.financial_exposure))).scalar()
    )
    total_exposure = Decimal(str(total_exposure_raw or "0.00"))

    # Exception rate
    exception_rate = round((exception_count / total * 100) if total > 0 else 0.0, 2)

    # Top exception types by count
    top_types_rows = db.execute(
        select(ExceptionRecord.exception_type, func.count(ExceptionRecord.exception_id).label("count"))
        .group_by(ExceptionRecord.exception_type)
        .order_by(func.count(ExceptionRecord.exception_id).desc())
        .limit(6)
    ).all()
    top_exception_types = [
        {"exception_type": row.exception_type, "count": row.count}
        for row in top_types_rows
    ]

    return DashboardKPISchema(
        total_transactions=total,
        healthy_count=healthy,
        exception_count=exception_count,
        open_exceptions=open_exc,
        auto_resolved_exceptions=auto_resolved,
        total_financial_exposure=format(total_exposure, "f"),
        exception_rate_pct=exception_rate,
        top_exception_types=top_exception_types,
    )
