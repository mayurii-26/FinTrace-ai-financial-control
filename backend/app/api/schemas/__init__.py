"""Pydantic v2 request / response schemas for the FinTrace API.

All monetary values are serialized as strings to preserve Decimal precision
over the wire (no float rounding surprises).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _DecimalModel(BaseModel):
    """Base with shared Decimal serializer."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "financial_exposure",
        "order_amount",
        "payment_amount",
        "refund_amount",
        "fee_amount",
        "tax_amount",
        "expected_settlement",
        "actual_settlement",
        "bank_credit",
        "total_financial_exposure",
        "total_financial_value",
        check_fields=False,
    )
    def _str_decimal(self, v: Decimal) -> str:
        return format(v, "f") if isinstance(v, Decimal) else str(v)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardKPISchema(BaseModel):
    total_transactions: int
    healthy_count: int
    exception_count: int
    open_exceptions: int
    auto_resolved_exceptions: int
    total_financial_exposure: str  # Decimal as string
    exception_rate_pct: float
    top_exception_types: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ExceptionListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exception_id: str
    transaction_id: str
    exception_type: str
    severity: str
    financial_exposure: str
    status: str
    detected_at: datetime
    ground_truth_type: Optional[str] = None


class ExceptionDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exception_id: str
    transaction_id: str
    exception_type: str
    severity: str
    financial_exposure: str
    status: str
    detected_at: datetime
    control_evidence: Dict[str, Any]
    ground_truth_type: Optional[str] = None
    investigations: List["InvestigationSchema"] = []


class ExceptionFilterParams(BaseModel):
    exception_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    min_exposure: Optional[float] = None
    max_exposure: Optional[float] = None
    limit: int = 50
    offset: int = 0

    @field_validator("limit")
    @classmethod
    def cap_limit(cls, v: int) -> int:
        return min(v, 500)


# ---------------------------------------------------------------------------
# Transaction lifecycle
# ---------------------------------------------------------------------------

class TransactionLifecycleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    status: str
    exception_type: Optional[str] = None
    financial_exposure: str
    ground_truth_type: str
    ground_truth_is_anomaly: bool

    order_amount: str
    payment_amount: str
    refund_amount: str
    fee_amount: str
    tax_amount: str
    expected_settlement: str
    actual_settlement: str
    bank_credit: str

    payment_timestamp: Optional[datetime] = None
    settlement_timestamp: Optional[datetime] = None
    bank_timestamp: Optional[datetime] = None

    has_order: bool
    has_payment: bool
    has_refund: bool
    has_settlement: bool
    has_bank_entry: bool


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------

class InvestigationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigation_id: str
    exception_id: str
    transaction_id: str
    agent_provider: str
    root_cause: str
    explanation: str
    recommended_action: str
    confidence: float
    evidence: Dict[str, Any]
    created_at: datetime


class InvestigationRequestSchema(BaseModel):
    exception_id: str
    provider: str = "mock"  # "mock" | "openai"


class InvestigationResponseSchema(BaseModel):
    investigation: InvestigationSchema
    requires_human_review: bool
    missing_evidence: List[str]


# ---------------------------------------------------------------------------
# Reconciliation / control execution
# ---------------------------------------------------------------------------

class ReconciliationRequestSchema(BaseModel):
    transaction_ids: Optional[List[str]] = None  # None → run on all PENDING
    force_rerun: bool = False


class ReconciliationResultItemSchema(BaseModel):
    transaction_id: str
    status: str
    exception_type: Optional[str] = None
    financial_exposure: str
    exception_id: Optional[str] = None


class ReconciliationResponseSchema(BaseModel):
    processed: int
    healthy: int
    exceptions_raised: int
    results: List[ReconciliationResultItemSchema]
    duration_seconds: float


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

class BenchmarkResponseSchema(BaseModel):
    total_records: int
    healthy_count: int
    exception_count: int

    # Detection quality
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    match_rate_pct: float

    # Financial
    total_financial_value: str
    total_financial_exposure: str

    # Exception resolution
    open_exceptions: int
    auto_resolved_exceptions: int
    approved_exceptions: int
    rejected_exceptions: int

    # Performance
    throughput_records_per_sec: float
    duration_seconds: float

    # Per-type breakdown
    per_type_stats: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

class SeedRequestSchema(BaseModel):
    count: Optional[int] = None
    seed: Optional[int] = None
    force: bool = False


class SeedResponseSchema(BaseModel):
    inserted: int
    message: str


# Forward-ref resolution
ExceptionDetailSchema.model_rebuild()
