"""LLM provider abstraction for the FinTrace AI investigation agent.

Providers
---------
  mock    Deterministic offline heuristics. No API key required.
          Used by default and in all tests. Always available.

  openai  OpenAI chat completions with tool calling.
          Requires OPENAI_API_KEY in backend environment variables.
          Falls back transparently to MockProvider when:
            - OPENAI_API_KEY is not set or empty
            - openai package is not installed
            - API call raises any exception (timeout, auth error, rate-limit, etc.)

New providers can be added by implementing BaseProvider and registering
in get_provider().
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default HTTP timeout for OpenAI API calls (seconds).
# Long enough for a multi-tool investigation; short enough to fail fast.
_OPENAI_TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """Abstract LLM provider. Providers do not perform financial calculations."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can handle requests right now."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Send a completion request.

        Returns:
            (text_response, list_of_tool_calls)
            text_response:  the final JSON string from the model
            list_of_tool_calls: [{"name": ..., "arguments": {...}}, ...]
                                Only calls the model actually requested.
        """


# ---------------------------------------------------------------------------
# Mock provider  (deterministic heuristics, no external calls)
# ---------------------------------------------------------------------------

# Per-exception-type heuristic investigation plans.
_MOCK_PLANS: Dict[str, Dict[str, Any]] = {
    "settlement_amount_discrepancy": {
        "tools": ["get_control_evidence", "get_financial_timeline", "get_settlements"],
        "confidence": 0.92,
        "recommended_action": "raise_dispute",
    },
    "refund_closure_failure": {
        "tools": ["get_control_evidence", "get_refunds", "get_settlements", "get_financial_timeline"],
        "confidence": 0.91,
        "recommended_action": "initiate_clawback",
    },
    "duplicate_financial_event": {
        "tools": ["get_control_evidence", "get_payments", "get_financial_timeline"],
        "confidence": 0.93,
        "recommended_action": "refund_duplicate",
    },
    "orphan_financial_event": {
        "tools": ["get_control_evidence", "get_payments", "get_settlements", "get_bank_entries"],
        "confidence": 0.88,
        "recommended_action": "investigate_manually",
    },
    "missing_downstream_event": {
        "tools": ["get_control_evidence", "get_financial_timeline", "get_settlements", "get_bank_entries"],
        "confidence": 0.75,
        "recommended_action": "escalate_to_gateway",
    },
    "settlement_timing_anomaly": {
        "tools": ["get_control_evidence", "get_financial_timeline"],
        "confidence": 0.90,
        "recommended_action": "monitor_and_escalate",
    },
}

_DEFAULT_PLAN: Dict[str, Any] = {
    "tools": ["get_control_evidence", "get_financial_timeline"],
    "confidence": 0.55,
    "recommended_action": "investigate_manually",
}

_MISSING_EVIDENCE_MAP: Dict[str, List[str]] = {
    "settlement_amount_discrepancy": ["gateway_fee_schedule", "raw_gateway_webhook_payload"],
    "refund_closure_failure": ["refund_gateway_confirmation", "merchant_statement"],
    "duplicate_financial_event": ["gateway_payment_logs", "customer_bank_statement"],
    "orphan_financial_event": ["gateway_reconciliation_file", "webhook_delivery_logs"],
    "missing_downstream_event": ["gateway_settlement_report", "bank_statement"],
    "settlement_timing_anomaly": ["gateway_sla_contract", "processing_queue_logs"],
}


class MockProvider(BaseProvider):
    """Deterministic heuristic provider.

    Executes the correct tools for the exception type, reads their results,
    and builds a response using only pre-computed values from those results.
    Never makes external calls.
    """

    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def get_tool_plan(self, exception_type: str) -> Dict[str, Any]:
        return _MOCK_PLANS.get(exception_type, _DEFAULT_PLAN)

    def build_response(
        self,
        exception_type: str,
        tool_results: Dict[str, Any],
    ) -> str:
        """Build the final JSON response using actual tool result data."""
        plan = self.get_tool_plan(exception_type)
        ctrl       = tool_results.get("get_control_evidence", {})
        timeline   = tool_results.get("get_financial_timeline", {})
        payments   = tool_results.get("get_payments", {})
        refunds    = tool_results.get("get_refunds", {})
        settlements= tool_results.get("get_settlements", {})
        bank_entries = tool_results.get("get_bank_entries", {})

        root_cause   = self._derive_root_cause(exception_type, ctrl, payments, refunds, settlements, timeline)
        impact_summary = self._derive_impact(exception_type, ctrl)
        recommendation = self._derive_recommendation(exception_type, ctrl, plan)
        evidence     = self._extract_key_evidence(ctrl, payments, refunds, settlements, bank_entries, timeline)

        return json.dumps({
            "root_cause": root_cause,
            "impact_summary": impact_summary,
            "evidence": evidence,
            "missing_evidence": _MISSING_EVIDENCE_MAP.get(exception_type, []),
            "confidence": plan["confidence"],
            "recommendation": recommendation,
            "recommended_action": plan["recommended_action"],
            "requires_human_review": plan["confidence"] < 0.90,
        })

    # ------------------------------------------------------------------
    # Private derivation helpers
    # ------------------------------------------------------------------

    def _derive_root_cause(
        self,
        exc_type: str,
        ctrl: Dict[str, Any],
        payments: Dict[str, Any],
        refunds: Dict[str, Any],
        settlements: Dict[str, Any],
        timeline: Dict[str, Any],
    ) -> str:
        ctrl_ev = ctrl.get("control_evidence", {})

        if exc_type == "settlement_amount_discrepancy":
            diff   = ctrl_ev.get("settlement_consistency_diff", "unknown")
            sets   = settlements.get("settlements", [{}])
            expected = sets[0].get("expected_settlement", "?") if sets else "?"
            actual   = sets[0].get("actual_settlement", "?") if sets else "?"
            return (
                f"Settlement amount {actual} received from payment gateway differs "
                f"from the control-engine-computed expected settlement of {expected} "
                f"by {diff}. This indicates an undisclosed deduction or fee-rate mismatch."
            )
        if exc_type == "refund_closure_failure":
            total_refund = refunds.get("total_refund_amount", "unknown")
            sets = settlements.get("settlements", [{}])
            actual = sets[0].get("actual_settlement", "?") if sets else "?"
            return (
                f"A refund of {total_refund} was issued but the settlement of {actual} "
                f"was computed on the gross order amount, ignoring the refund. "
                f"The merchant was over-settled by the refund amount net of fees."
            )
        if exc_type == "duplicate_financial_event":
            count    = payments.get("count", 2)
            pay_list = payments.get("payments", [])
            amounts  = [p.get("amount") for p in pay_list]
            return (
                f"{count} payment records found for the same transaction "
                f"(amounts: {', '.join(str(a) for a in amounts[:3])}). "
                f"The duplicate payments passed gateway validation without deduplication."
            )
        if exc_type == "orphan_financial_event":
            orphan_count = payments.get("orphan_count", 1)
            orphan_pays  = [p for p in payments.get("payments", []) if p.get("is_orphan")]
            ids = [p.get("payment_id", "?") for p in orphan_pays[:2]]
            return (
                f"{orphan_count} orphan payment record(s) (IDs: {', '.join(ids)}) "
                f"exist with no matching parent order in the transaction lifecycle. "
                f"This indicates a webhook race condition or pipeline data loss."
            )
        if exc_type == "missing_downstream_event":
            missing = ctrl_ev.get("missing_stages", [])
            events  = timeline.get("event_count", 0)
            return (
                f"Payment was captured ({events} lifecycle events recorded) but stages "
                f"{missing} were never received. The merchant has not been credited."
            )
        if exc_type == "settlement_timing_anomaly":
            s_days = ctrl_ev.get("settlement_days_late", 0)
            b_days = ctrl_ev.get("bank_days_late", 0)
            return (
                f"Settlement arrived {s_days} day(s) after payment (SLA: 3 days); "
                f"bank credit arrived {b_days} day(s) after settlement (SLA: 2 days). "
                f"Both SLA windows were breached."
            )
        return (
            f"Exception type {exc_type} detected; "
            f"insufficient heuristic template for auto root-cause derivation."
        )

    def _derive_impact(self, exc_type: str, ctrl: Dict[str, Any]) -> str:
        exposure = ctrl.get("financial_exposure", "unknown")
        severity = ctrl.get("severity", "unknown")
        impacts: Dict[str, str] = {
            "settlement_amount_discrepancy": (
                f"Merchant under-credited by {exposure} (severity: {severity}). "
                f"Recurring occurrences compound revenue loss."
            ),
            "refund_closure_failure": (
                f"Merchant over-settled by {exposure}. "
                f"Liability exposure until clawback completes."
            ),
            "duplicate_financial_event": (
                f"Customer over-charged by {exposure}. "
                f"Risk of chargeback and regulatory action."
            ),
            "orphan_financial_event": (
                f"{exposure} in unattributed funds present in the ledger. "
                f"Audit risk if unresolved."
            ),
            "missing_downstream_event": (
                f"{exposure} in payment received but not settled to merchant. "
                f"Revenue at risk until settlement arrives."
            ),
            "settlement_timing_anomaly": (
                f"{exposure} in delayed settlement (severity: {severity}). "
                f"SLA breach may trigger contractual penalties."
            ),
        }
        return impacts.get(exc_type, f"Financial exposure of {exposure} (severity: {severity}).")

    def _derive_recommendation(
        self,
        exc_type: str,
        ctrl: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> str:
        ctrl_ev = ctrl.get("control_evidence", {})
        recs: Dict[str, str] = {
            "settlement_amount_discrepancy": (
                "Raise a formal dispute with the payment gateway. Attach the control "
                "evidence showing the settlement_consistency_diff and request a "
                "reconciliation statement."
            ),
            "refund_closure_failure": (
                "Initiate a clawback for the over-settled amount. Verify the refund "
                "was credited to the customer before closing."
            ),
            "duplicate_financial_event": (
                "Identify the duplicate payment ID and issue a refund to the customer. "
                "Investigate the gateway deduplication gap."
            ),
            "orphan_financial_event": (
                "Investigate each orphan record manually against gateway webhook logs "
                "to determine whether real money moved."
            ),
            "missing_downstream_event": (
                f"Escalate to the payment gateway to trace the settlement for missing "
                f"stages: {ctrl_ev.get('missing_stages', [])}."
            ),
            "settlement_timing_anomaly": (
                "Document the SLA breach with timestamps and escalate to the gateway "
                "account manager. Monitor for a recurring pattern."
            ),
        }
        return recs.get(exc_type, f"Take action: {plan['recommended_action']}.")

    def _extract_key_evidence(
        self,
        ctrl: Dict[str, Any],
        payments: Dict[str, Any],
        refunds: Dict[str, Any],
        settlements: Dict[str, Any],
        bank_entries: Dict[str, Any],
        timeline: Dict[str, Any],
    ) -> Dict[str, Any]:
        ctrl_ev = ctrl.get("control_evidence", {})
        return {
            "control_engine_flags": {
                k: v for k, v in ctrl_ev.items()
                if k in (
                    "settlement_consistency_diff",
                    "amount_integrity_diff",
                    "settlement_days_late",
                    "bank_days_late",
                    "duplicate_details",
                    "orphan_details",
                    "missing_stages",
                    "refund_present",
                    "lifecycle_completeness_ok",
                )
            },
            "payments_count": payments.get("count"),
            "orphan_payment_count": payments.get("orphan_count"),
            "duplicate_detected": payments.get("duplicate_detected"),
            "refund_present": refunds.get("refund_present", False),
            "total_refund": refunds.get("total_refund_amount"),
            "settlements_count": settlements.get("count"),
            "bank_entries_count": bank_entries.get("count"),
            "timeline_events": timeline.get("event_count"),
        }

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        raise NotImplementedError(
            "MockProvider uses get_tool_plan / build_response directly; "
            "complete() is not called in the mock investigation path."
        )


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseProvider):
    """OpenAI chat completions with tool calling.

    Falls back to MockProvider if:
      - api_key is empty / not set
      - openai package is not installed
      - any API call raises an exception (network error, timeout, auth, etc.)

    The fallback is transparent — callers receive a valid InvestigationOutput
    regardless of whether OpenAI was reachable.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key.strip()
        self._model   = model
        self._client  = None

        if self._api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    timeout=_OPENAI_TIMEOUT_SECONDS,
                )
                logger.info("OpenAI provider initialised (model=%s)", self._model)
            except ImportError:
                logger.error(
                    "openai package is not installed. "
                    "Run: pip install openai  — falling back to mock."
                )
            except Exception as exc:
                logger.error(
                    "Failed to initialise OpenAI client: %s — falling back to mock.", exc
                )
        else:
            logger.debug(
                "OPENAI_API_KEY is not set — OpenAI provider will not be used."
            )

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        """Return True only when the client was initialised successfully."""
        return self._client is not None and bool(self._api_key)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Single-turn completion (used for the final JSON conclusion call).

        Raises RuntimeError if the provider is not available — callers
        should check is_available() or catch this and fall back.
        """
        if not self.is_available():
            raise RuntimeError(
                "OpenAI provider is not available "
                "(API key missing or client failed to initialise)."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        kwargs: Dict[str, Any] = {
            "model":       self._model,
            "messages":    messages,
            "temperature": 0.1,
            "max_tokens":  2048,
        }
        if tools:
            kwargs["tools"]       = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
        except Exception as exc:
            raise RuntimeError(f"OpenAI API call failed: {exc}") from exc

        msg = response.choices[0].message

        # Collect any tool calls the model requested
        tool_calls: List[Dict[str, Any]] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"name": tc.function.name, "arguments": args})

        return msg.content or "{}", tool_calls


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def get_provider(provider_name: str) -> BaseProvider:
    """Return the requested provider, falling back to MockProvider on any issue.

    Fallback conditions for 'openai':
      - OPENAI_API_KEY is empty
      - openai package is not installed
      - OpenAI client initialisation raised an exception
    """
    from app.core.config import get_settings
    settings = get_settings()

    if provider_name == "openai":
        p = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        if p.is_available():
            logger.info(
                "Using OpenAI provider (model=%s)", settings.openai_model
            )
            return p
        logger.warning(
            "OpenAI provider unavailable (OPENAI_API_KEY not set or client failed); "
            "falling back to MockProvider."
        )

    return MockProvider()
