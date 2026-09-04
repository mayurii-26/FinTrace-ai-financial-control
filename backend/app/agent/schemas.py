"""Structured output schemas for the FinTrace AI investigation agent.

These Pydantic models define the canonical shape of every investigation
result, tool call record, and lifecycle trace produced by the agent.
They are the single source of truth for what the agent can return.

Confidence rules (enforced at validation time):
    >= 0.90  →  high_confidence   recommendation can be acted on directly
    0.70–0.89 → requires_verification  controller must review before action
    < 0.70   →  insufficient_evidence  must trigger manual review
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RecommendedAction(str, enum.Enum):
    RAISE_DISPUTE = "raise_dispute"
    INITIATE_CLAWBACK = "initiate_clawback"
    REFUND_DUPLICATE = "refund_duplicate"
    INVESTIGATE_MANUALLY = "investigate_manually"
    ESCALATE_TO_GATEWAY = "escalate_to_gateway"
    MONITOR_AND_ESCALATE = "monitor_and_escalate"
    AUTO_RESOLVE = "auto_resolve"


class ConfidenceBand(str, enum.Enum):
    HIGH = "high_confidence"              # >= 0.90
    REQUIRES_VERIFICATION = "requires_verification"  # 0.70 – 0.89
    INSUFFICIENT = "insufficient_evidence"           # < 0.70


class StageStatus(str, enum.Enum):
    VALID = "VALID"
    WARNING = "WARNING"
    BREAK = "BREAK"
    MISSING = "MISSING"


class ControllerActionType(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"


class VerificationStatus(str, enum.Enum):
    RESOLVED = "resolved"
    PERSISTS = "persists"
    IMPROVED = "improved"


# ---------------------------------------------------------------------------
# Tool call record – only tools that were actually executed are recorded
# ---------------------------------------------------------------------------

class ToolCallRecord(BaseModel):
    """A single tool invocation made by the agent during investigation."""

    tool_name: str
    arguments: Dict[str, Any]
    result_summary: str        # short human-readable summary of what was found
    executed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Lifecycle stage – used in the financial lifecycle trace
# ---------------------------------------------------------------------------

class LifecycleStage(BaseModel):
    """One stage in the ORDER → BANK_CREDIT lifecycle."""

    stage: str                          # e.g. "ORDER", "PAYMENT", "SETTLEMENT"
    status: StageStatus
    amount: Optional[str] = None        # Decimal serialized as string
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None         # human-readable explanation of status
    raw_ids: List[str] = Field(default_factory=list)  # relevant DB IDs


class LifecycleTrace(BaseModel):
    """Full financial lifecycle trace with per-stage statuses."""

    transaction_id: str
    stages: List[LifecycleStage]
    overall_status: StageStatus          # worst stage status
    exception_type: Optional[str] = None
    financial_exposure: str = "0.00"    # Decimal as string
    traced_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Core investigation output
# ---------------------------------------------------------------------------

class InvestigationOutput(BaseModel):
    """Structured result returned by the AI agent for one exception.

    This is the canonical investigation contract. Every field is required
    except ``missing_evidence`` (may be empty) and ``tool_calls`` (agent
    populates only actually-executed calls).
    """

    model_config = ConfigDict(use_enum_values=True)

    # Exception identity
    exception_id: str
    exception_type: str
    severity: str

    # Agent findings
    root_cause: str = Field(
        description=(
            "1-2 sentence factual statement of the root cause based solely on "
            "evidence returned by tool calls. Never invented."
        )
    )
    evidence: Dict[str, Any] = Field(
        description="Key evidence values read from the database via tools."
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Named data sources that would improve confidence but are unavailable.",
    )

    # Financial impact (all values from deterministic engine – never computed by LLM)
    financial_exposure: str  # Decimal as string
    impact_summary: str       # human-readable impact description

    # Recommendation
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    recommendation: str       # plain-English next step
    recommended_action: RecommendedAction
    requires_human_review: bool

    # Traceability
    agent_provider: str
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    lifecycle_trace: Optional[LifecycleTrace] = None
    investigated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("confidence_band", mode="before")
    @classmethod
    def derive_confidence_band(cls, v: Any, info: Any) -> ConfidenceBand:
        """Auto-derive the band from the confidence score if not set explicitly."""
        if isinstance(v, ConfidenceBand):
            return v
        # Allow explicit string pass-through
        if isinstance(v, str) and v in ConfidenceBand._value2member_map_:
            return ConfidenceBand(v)
        # Derive from the confidence field value when available
        confidence = (info.data or {}).get("confidence")
        if confidence is not None:
            return confidence_to_band(float(confidence))
        return ConfidenceBand.INSUFFICIENT

    @field_validator("requires_human_review", mode="before")
    @classmethod
    def enforce_human_review_for_low_confidence(cls, v: Any, info: Any) -> bool:
        """Always require human review when confidence is below 0.70."""
        confidence = (info.data or {}).get("confidence")
        if confidence is not None and float(confidence) < 0.70:
            return True
        return bool(v)


def confidence_to_band(confidence: float) -> ConfidenceBand:
    """Convert a 0-1 confidence score to the canonical confidence band."""
    if confidence >= 0.90:
        return ConfidenceBand.HIGH
    if confidence >= 0.70:
        return ConfidenceBand.REQUIRES_VERIFICATION
    return ConfidenceBand.INSUFFICIENT


# ---------------------------------------------------------------------------
# Controller action schemas
# ---------------------------------------------------------------------------

class ControllerActionRequest(BaseModel):
    """Request body for POST /api/exceptions/{id}/action."""

    action: ControllerActionType
    actor: str = "controller"
    notes: Optional[str] = None


class ControllerActionResponse(BaseModel):
    """Response for a controller action."""

    exception_id: str
    action: str
    previous_status: str
    new_status: str
    actor: str
    notes: Optional[str] = None
    actioned_at: datetime


# ---------------------------------------------------------------------------
# Verification schemas
# ---------------------------------------------------------------------------

class VerificationResponse(BaseModel):
    """Response for POST /api/exceptions/{id}/verify."""

    exception_id: str
    transaction_id: str
    before_exception_type: Optional[str]
    after_exception_type: Optional[str]
    before_exposure: str   # Decimal as string
    after_exposure: str    # Decimal as string
    verification_status: VerificationStatus
    control_result_summary: Dict[str, Any]
    verified_at: datetime
