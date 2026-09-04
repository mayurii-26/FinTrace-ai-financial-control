"""AI Investigation Agent for FinTrace.

Provides evidence-based root-cause investigation for detected exceptions.
The agent operates in two modes:

- ``mock``: Deterministic, offline heuristic analysis using only the
  control evidence already computed by the deterministic engine. No
  external calls, no API keys required. Production-quality structured
  output. Used by default and in tests.

- ``openai``: Sends a structured prompt to the OpenAI chat completions
  API and parses the JSON response. Requires ``OPENAI_API_KEY`` in env.

**Hard constraint**: The agent NEVER calculates, overrides or modifies
authoritative financial amounts. It reads only pre-computed values from
the control engine and presents reasoning over them.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.exception import ExceptionRecord, Investigation

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Investigation result dataclass
# ---------------------------------------------------------------------------

@dataclass
class InvestigationResult:
    root_cause: str
    explanation: str
    recommended_action: str
    confidence: float
    evidence: Dict[str, Any]
    missing_evidence: List[str]
    requires_human_review: bool
    agent_provider: str


# ---------------------------------------------------------------------------
# Evidence collector (read-only tools)
# ---------------------------------------------------------------------------

def _collect_evidence(db: Session, exception_record: ExceptionRecord) -> Dict[str, Any]:
    """Read all available evidence for the exception. Read-only."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.transaction import Transaction

    txn = db.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.order),
            selectinload(Transaction.payments),
            selectinload(Transaction.refunds),
            selectinload(Transaction.settlements),
            selectinload(Transaction.bank_entries),
        )
        .where(Transaction.transaction_id == exception_record.transaction_id)
    ).scalar_one_or_none()

    if txn is None:
        return {}

    def _d(v: Any) -> str:
        return format(v, "f") if isinstance(v, Decimal) else str(v) if v is not None else None

    evidence: Dict[str, Any] = {
        "transaction_id": txn.transaction_id,
        "ground_truth_type": txn.ground_truth_type,
        "control_evidence": exception_record.control_evidence,
        "exception_type": exception_record.exception_type,
        "severity": exception_record.severity,
        "financial_exposure": _d(exception_record.financial_exposure),
        "order": None,
        "payments": [],
        "refunds": [],
        "settlements": [],
        "bank_entries": [],
        "financial_timeline": [],
    }

    if txn.order:
        evidence["order"] = {
            "order_id": txn.order.order_id,
            "amount": _d(txn.order.amount),
            "created_at": txn.order.created_at.isoformat() if txn.order.created_at else None,
        }
        evidence["financial_timeline"].append({
            "stage": "order",
            "timestamp": txn.order.created_at.isoformat() if txn.order.created_at else None,
            "amount": _d(txn.order.amount),
        })

    for p in sorted(txn.payments, key=lambda x: x.payment_timestamp):
        evidence["payments"].append({
            "payment_id": p.payment_id,
            "amount": _d(p.amount),
            "status": p.status,
            "is_orphan": p.is_orphan,
            "timestamp": p.payment_timestamp.isoformat() if p.payment_timestamp else None,
        })
        evidence["financial_timeline"].append({
            "stage": "payment" + (" (orphan)" if p.is_orphan else ""),
            "timestamp": p.payment_timestamp.isoformat() if p.payment_timestamp else None,
            "amount": _d(p.amount),
        })

    for r in sorted(txn.refunds, key=lambda x: x.refund_timestamp):
        evidence["refunds"].append({
            "refund_id": r.refund_id,
            "amount": _d(r.amount),
            "status": r.status,
            "timestamp": r.refund_timestamp.isoformat() if r.refund_timestamp else None,
        })
        evidence["financial_timeline"].append({
            "stage": "refund",
            "timestamp": r.refund_timestamp.isoformat() if r.refund_timestamp else None,
            "amount": _d(r.amount),
        })

    for s in sorted(txn.settlements, key=lambda x: x.settlement_timestamp):
        evidence["settlements"].append({
            "settlement_id": s.settlement_id,
            "expected": _d(s.expected_settlement),
            "actual": _d(s.actual_settlement),
            "fee": _d(s.fee_amount),
            "tax": _d(s.tax_amount),
            "is_orphan": s.is_orphan,
            "timestamp": s.settlement_timestamp.isoformat() if s.settlement_timestamp else None,
        })
        evidence["financial_timeline"].append({
            "stage": "settlement" + (" (orphan)" if s.is_orphan else ""),
            "timestamp": s.settlement_timestamp.isoformat() if s.settlement_timestamp else None,
            "amount": _d(s.actual_settlement),
        })

    for b in sorted(txn.bank_entries, key=lambda x: x.bank_timestamp):
        evidence["bank_entries"].append({
            "bank_entry_id": b.bank_entry_id,
            "amount": _d(b.amount),
            "is_orphan": b.is_orphan,
            "timestamp": b.bank_timestamp.isoformat() if b.bank_timestamp else None,
        })
        evidence["financial_timeline"].append({
            "stage": "bank_credit" + (" (orphan)" if b.is_orphan else ""),
            "timestamp": b.bank_timestamp.isoformat() if b.bank_timestamp else None,
            "amount": _d(b.amount),
        })

    # Sort timeline chronologically
    evidence["financial_timeline"].sort(key=lambda x: x.get("timestamp") or "")

    return evidence


# ---------------------------------------------------------------------------
# Mock agent (deterministic heuristic, offline)
# ---------------------------------------------------------------------------

_MOCK_TEMPLATES: Dict[str, Dict[str, str]] = {
    "settlement_amount_discrepancy": {
        "root_cause": "Settlement amount received from payment gateway does not match the recomputed expected settlement derived from order amount minus standard fee/tax.",
        "explanation": (
            "The control engine recomputed the expected settlement independently "
            "using standard fee (2%) and tax (18% GST on fee) rates. The actual "
            "settlement credited differs by the amount shown in control_evidence "
            "settlement_consistency_diff. This typically indicates a fee-rate "
            "mismatch, an undisclosed deduction, or a platform processing error."
        ),
        "recommended_action": "raise_dispute",
    },
    "refund_closure_failure": {
        "root_cause": "A refund was issued to the customer but the corresponding settlement was calculated on the gross order amount, ignoring the refund. The merchant was over-settled.",
        "explanation": (
            "The refund_closure_failure indicates the settlement computation "
            "did not net off the refund amount. The merchant received more than "
            "they were entitled to post-refund. This creates a liability and "
            "must be reconciled by clawing back the over-settled amount."
        ),
        "recommended_action": "initiate_clawback",
    },
    "duplicate_financial_event": {
        "root_cause": "More than one payment event was recorded for the same order within a short time window, indicating a duplicate charge.",
        "explanation": (
            "The duplicate_financial_event flag is raised when the control engine "
            "detects multiple payment rows linked to the same transaction. The "
            "duplicate payments were not orphan-flagged, meaning they all passed "
            "gateway validation. This requires immediate deduplication and "
            "refund of the excess charge."
        ),
        "recommended_action": "refund_duplicate",
    },
    "orphan_financial_event": {
        "root_cause": "One or more financial events (payment, settlement or bank entry) exist with no matching parent record in the transaction lifecycle.",
        "explanation": (
            "Orphan events are stage-level records that cannot be traced back "
            "to a valid order. This typically results from a race condition "
            "during webhook processing or a data-pipeline bug. The orphan "
            "events must be investigated to determine whether they represent "
            "real money movement or ghost records."
        ),
        "recommended_action": "investigate_manually",
    },
    "missing_downstream_event": {
        "root_cause": "The payment was captured but no corresponding settlement or bank credit record was found within the observation window.",
        "explanation": (
            "A missing_downstream_event means the lifecycle is incomplete: "
            "money left the customer but has not been credited to the merchant "
            "account via settlement and bank transfer. This may be a delayed "
            "settlement still in transit or a lost event in the pipeline."
        ),
        "recommended_action": "escalate_to_gateway",
    },
    "settlement_timing_anomaly": {
        "root_cause": "Settlement or bank credit arrived outside the contractual SLA window (>3 days for settlement, >2 days for bank credit).",
        "explanation": (
            "The timing anomaly is flagged when the elapsed days between "
            "payment_timestamp and settlement_timestamp, or between "
            "settlement_timestamp and bank_timestamp, exceeds the configured "
            "SLA thresholds. Repeated breaches may indicate gateway-side "
            "processing issues or a need to renegotiate SLA terms."
        ),
        "recommended_action": "monitor_and_escalate",
    },
}

_MISSING_EVIDENCE_MAP: Dict[str, List[str]] = {
    "settlement_amount_discrepancy": ["gateway_fee_schedule", "raw_gateway_webhook_payload"],
    "refund_closure_failure": ["refund_gateway_confirmation", "merchant_statement"],
    "duplicate_financial_event": ["gateway_payment_logs", "customer_bank_statement"],
    "orphan_financial_event": ["gateway_reconciliation_file", "webhook_delivery_logs"],
    "missing_downstream_event": ["gateway_settlement_report", "bank_statement"],
    "settlement_timing_anomaly": ["gateway_sla_contract", "processing_queue_logs"],
}

_HUMAN_REVIEW_TYPES = {
    "duplicate_financial_event",
    "orphan_financial_event",
    "missing_downstream_event",
}


def _mock_investigate(
    exception_record: ExceptionRecord, evidence: Dict[str, Any]
) -> InvestigationResult:
    exc_type = exception_record.exception_type
    template = _MOCK_TEMPLATES.get(exc_type, {
        "root_cause": f"Unrecognised exception type: {exc_type}.",
        "explanation": "No heuristic template available for this exception type.",
        "recommended_action": "investigate_manually",
    })

    exposure = evidence.get("financial_exposure", "0.00")
    ctrl = evidence.get("control_evidence", {})

    explanation_suffix = ""
    if exc_type == "settlement_amount_discrepancy":
        diff = ctrl.get("settlement_consistency_diff", "N/A")
        explanation_suffix = f" The discrepancy amount is ₹{diff}."
    elif exc_type == "settlement_timing_anomaly":
        s_days = ctrl.get("settlement_days_late", 0)
        b_days = ctrl.get("bank_days_late", 0)
        explanation_suffix = f" Settlement was {s_days}d late; bank credit was {b_days}d late."
    elif exc_type == "duplicate_financial_event":
        dup_details = ctrl.get("duplicate_details", [])
        explanation_suffix = f" Duplicate stages: {dup_details}."

    # Confidence is higher when the exception type is well-defined and
    # the financial evidence is unambiguous.
    confidence = 0.92 if exc_type in _MOCK_TEMPLATES else 0.55
    if exc_type in ("missing_downstream_event",):
        confidence = 0.75  # slightly lower - could be pipeline lag

    return InvestigationResult(
        root_cause=template["root_cause"],
        explanation=template["explanation"] + explanation_suffix,
        recommended_action=template["recommended_action"],
        confidence=confidence,
        evidence={
            "financial_exposure": exposure,
            "control_evidence_summary": {
                k: v for k, v in ctrl.items()
                if k in (
                    "amount_integrity_diff",
                    "settlement_consistency_diff",
                    "settlement_days_late",
                    "bank_days_late",
                    "duplicate_details",
                    "orphan_details",
                    "missing_stages",
                )
            },
            "payments_count": len(evidence.get("payments", [])),
            "refunds_count": len(evidence.get("refunds", [])),
            "settlements_count": len(evidence.get("settlements", [])),
            "bank_entries_count": len(evidence.get("bank_entries", [])),
            "timeline_length": len(evidence.get("financial_timeline", [])),
        },
        missing_evidence=_MISSING_EVIDENCE_MAP.get(exc_type, []),
        requires_human_review=exc_type in _HUMAN_REVIEW_TYPES,
        agent_provider="mock",
    )


# ---------------------------------------------------------------------------
# OpenAI agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a financial reconciliation AI agent for FinTrace.

Your job is to investigate detected payment exceptions by reasoning over
provided evidence. You MUST NOT calculate, recompute or override any
monetary amounts - all financial figures are pre-computed by the
deterministic control engine and are authoritative.

Respond ONLY with a valid JSON object with these exact keys:
- root_cause: string (1-2 sentences)
- explanation: string (2-4 sentences)
- recommended_action: one of [raise_dispute, initiate_clawback, refund_duplicate,
  investigate_manually, escalate_to_gateway, monitor_and_escalate, auto_resolve]
- confidence: float 0.0-1.0
- missing_evidence: list of strings
- requires_human_review: boolean
"""


def _openai_investigate(
    exception_record: ExceptionRecord, evidence: Dict[str, Any]
) -> InvestigationResult:
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed; falling back to mock agent.")
        return _mock_investigate(exception_record, evidence)

    api_key = settings.openai_api_key
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; falling back to mock agent.")
        return _mock_investigate(exception_record, evidence)

    client = OpenAI(api_key=api_key)

    user_content = json.dumps({
        "exception_type": exception_record.exception_type,
        "severity": exception_record.severity,
        "financial_exposure": format(exception_record.financial_exposure, "f"),
        "evidence": evidence,
    }, default=str, indent=2)

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as exc:
        logger.error("OpenAI investigation failed: %s. Falling back to mock.", exc)
        return _mock_investigate(exception_record, evidence)

    return InvestigationResult(
        root_cause=parsed.get("root_cause", ""),
        explanation=parsed.get("explanation", ""),
        recommended_action=parsed.get("recommended_action", "investigate_manually"),
        confidence=float(parsed.get("confidence", 0.5)),
        evidence=evidence,
        missing_evidence=parsed.get("missing_evidence", []),
        requires_human_review=bool(parsed.get("requires_human_review", True)),
        agent_provider="openai",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def investigate(
    db: Session,
    exception_id: str,
    provider: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Run an investigation for the given exception_id.

    Returns the saved Investigation row as a dict, or None if the
    exception was not found.
    """
    from sqlalchemy import select

    exc_record = db.execute(
        select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
    ).scalar_one_or_none()

    if exc_record is None:
        return None

    chosen_provider = provider or settings.llm_provider
    evidence = _collect_evidence(db, exc_record)

    if chosen_provider == "openai":
        result = _openai_investigate(exc_record, evidence)
    else:
        result = _mock_investigate(exc_record, evidence)

    inv = Investigation(
        exception_id=exc_record.exception_id,
        transaction_id=exc_record.transaction_id,
        agent_provider=result.agent_provider,
        root_cause=result.root_cause,
        explanation=result.explanation,
        recommended_action=result.recommended_action,
        confidence=result.confidence,
        evidence=result.evidence,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    return {
        "investigation": inv,
        "requires_human_review": result.requires_human_review,
        "missing_evidence": result.missing_evidence,
    }
