"""Core investigation agent for FinTrace.

Implements the full investigation flow:
    DETECTED -> INVESTIGATE -> EVIDENCE -> ROOT CAUSE -> IMPACT -> RECOMMEND

The agent:
1. Loads the exception and its context from the database.
2. Executes read-only tools to gather evidence (only tools that are
   actually called are recorded in tool_calls).
3. Builds a structured InvestigationOutput using either the mock heuristic
   engine or an OpenAI model with iterative tool calling.
4. Persists the Investigation ORM row and audit log entries.
5. Returns the full InvestigationOutput.

Design principle: "Deterministic finance. Probabilistic intelligence."
  - The deterministic control engine is the sole source of truth for all
    monetary values.
  - The agent never recalculates or overrides them.
  - If OpenAI is unreachable for any reason, the mock provider runs instead
    and an audit record notes the fallback.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.prompts import (
    OPENAI_TOOLS,
    SYSTEM_PROMPT,
    build_initial_prompt,
    build_investigation_prompt,
)
from app.agent.provider import MockProvider, OpenAIProvider, get_provider
from app.agent.schemas import (
    ConfidenceBand,
    InvestigationOutput,
    LifecycleTrace,
    RecommendedAction,
    ToolCallRecord,
    confidence_to_band,
)
from app.agent.tools import execute_tool
from app.audit.logger import log_action
from app.finance.lifecycle_trace import build_lifecycle_trace
from app.models.exception import ExceptionRecord, ExceptionStatus, Investigation

logger = logging.getLogger(__name__)

# Safety cap: max tool-call rounds before we force a conclusion.
_MAX_TOOL_ROUNDS = 6


# ---------------------------------------------------------------------------
# Investigation persistence helper
# ---------------------------------------------------------------------------

def _persist_investigation(
    db: Session,
    output: InvestigationOutput,
    exception_record: ExceptionRecord,
    fallback_used: bool = False,
) -> Investigation:
    """Write the investigation result to the DB and create audit entries."""

    inv = Investigation(
        exception_id=output.exception_id,
        transaction_id=exception_record.transaction_id,
        agent_provider=output.agent_provider,
        root_cause=output.root_cause,
        explanation=output.recommendation,
        recommended_action=output.recommended_action,
        confidence=output.confidence,
        evidence={
            "evidence": output.evidence,
            "missing_evidence": output.missing_evidence,
            "impact_summary": output.impact_summary,
            "confidence_band": output.confidence_band,
            "requires_human_review": output.requires_human_review,
            "tool_calls": [tc.model_dump(mode="json") for tc in output.tool_calls],
            "lifecycle_trace": (
                output.lifecycle_trace.model_dump(mode="json")
                if output.lifecycle_trace else None
            ),
            "fallback_used": fallback_used,
        },
    )
    db.add(inv)
    db.flush()

    # Audit: investigation completed
    log_action(
        db,
        action="investigation_created",
        transaction_id=exception_record.transaction_id,
        exception_id=exception_record.exception_id,
        actor=f"agent:{output.agent_provider}",
        details={
            "investigation_id": inv.investigation_id,
            "provider": output.agent_provider,
            "confidence": output.confidence,
            "confidence_band": output.confidence_band,
            "recommended_action": output.recommended_action,
            "requires_human_review": output.requires_human_review,
            "tool_calls_count": len(output.tool_calls),
            "fallback_used": fallback_used,
        },
        message=(
            f"AI investigation completed | provider={output.agent_provider} "
            f"| confidence={output.confidence:.2f} ({output.confidence_band}) "
            f"| action={output.recommended_action}"
            + (" | FALLBACK: mock used due to OpenAI error" if fallback_used else "")
        ),
    )

    # Audit: each tool call executed
    for tc in output.tool_calls:
        log_action(
            db,
            action="investigation_tool_call",
            transaction_id=exception_record.transaction_id,
            exception_id=exception_record.exception_id,
            actor=f"agent:{output.agent_provider}",
            details={
                "tool": tc.tool_name,
                "arguments": tc.arguments,
                "result_summary": tc.result_summary,
            },
            message=f"Tool executed: {tc.tool_name} -> {tc.result_summary}",
        )

    return inv


# ---------------------------------------------------------------------------
# Mock investigation flow
# ---------------------------------------------------------------------------

def _run_mock_investigation(
    db: Session,
    exception_record: ExceptionRecord,
    lifecycle_trace: LifecycleTrace,
) -> InvestigationOutput:
    """Run the deterministic mock investigation.

    Executes the tool plan for the exception type, builds a structured
    response from actual DB data, and returns InvestigationOutput.
    """
    provider = MockProvider()
    plan     = provider.get_tool_plan(exception_record.exception_type)

    tool_calls: List[ToolCallRecord] = []
    tool_results: Dict[str, Any] = {}
    txn_id = exception_record.transaction_id
    exc_id = exception_record.exception_id

    for tool_name in plan["tools"]:
        args = (
            {"exception_id": exc_id}
            if tool_name == "get_control_evidence"
            else {"transaction_id": txn_id}
        )
        result, record = execute_tool(db, tool_name, args)
        tool_calls.append(record)
        tool_results[tool_name] = result

    response_json = provider.build_response(exception_record.exception_type, tool_results)

    try:
        parsed = json.loads(response_json)
    except json.JSONDecodeError:
        parsed = {}

    confidence = float(parsed.get("confidence", plan["confidence"]))
    band       = confidence_to_band(confidence)

    return InvestigationOutput(
        exception_id=exc_id,
        exception_type=exception_record.exception_type,
        severity=exception_record.severity,
        root_cause=parsed.get("root_cause", "Root cause could not be determined."),
        evidence=parsed.get("evidence", {}),
        missing_evidence=parsed.get("missing_evidence", []),
        financial_exposure=format(exception_record.financial_exposure, "f"),
        impact_summary=parsed.get("impact_summary", ""),
        confidence=confidence,
        confidence_band=band,
        recommendation=parsed.get("recommendation", ""),
        recommended_action=RecommendedAction(
            parsed.get("recommended_action", "investigate_manually")
        ),
        requires_human_review=confidence < 0.90,
        agent_provider="mock",
        tool_calls=tool_calls,
        lifecycle_trace=lifecycle_trace,
    )


# ---------------------------------------------------------------------------
# OpenAI tool-calling investigation flow
# ---------------------------------------------------------------------------

def _run_openai_investigation(
    db: Session,
    exception_record: ExceptionRecord,
    lifecycle_trace: LifecycleTrace,
    provider: OpenAIProvider,
) -> tuple[InvestigationOutput, bool]:
    """Run an OpenAI-powered investigation with iterative tool calling.

    Returns:
        (InvestigationOutput, fallback_used)
        fallback_used is True when we had to fall back to mock.
    """
    txn_id = exception_record.transaction_id
    exc_id = exception_record.exception_id

    # Build initial conversation
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_initial_prompt(
                exception_id=exc_id,
                transaction_id=txn_id,
                exception_type=exception_record.exception_type,
                severity=exception_record.severity,
                financial_exposure=format(exception_record.financial_exposure, "f"),
            ),
        },
    ]

    tool_calls_executed: List[ToolCallRecord] = []
    all_tool_results: Dict[str, Any] = {}

    # ── Iterative tool-calling loop ───────────────────────────────────────
    for _round in range(_MAX_TOOL_ROUNDS):
        try:
            response = provider._client.chat.completions.create(  # type: ignore[union-attr]
                model=provider._model,
                messages=messages,
                tools=OPENAI_TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error(
                "OpenAI API call failed on tool-calling round %d for exception %s: %s. "
                "Falling back to mock.", _round + 1, exc_id, exc
            )
            mock_output = _run_mock_investigation(db, exception_record, lifecycle_trace)
            return mock_output, True

        msg           = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Append assistant turn to conversation history
        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": msg.content,
        }
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        if finish_reason == "tool_calls" and msg.tool_calls:
            # Execute each requested tool and feed results back
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                result, record = execute_tool(db, tool_name, args)
                tool_calls_executed.append(record)
                all_tool_results[tool_name] = result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
        else:
            # Model finished its tool loop naturally
            break

    # ── Final conclusion call ─────────────────────────────────────────────
    # Ask the model to emit its structured JSON conclusion.
    conclusion_prompt = build_investigation_prompt(
        exception_id=exc_id,
        transaction_id=txn_id,
        exception_type=exception_record.exception_type,
        severity=exception_record.severity,
        financial_exposure=format(exception_record.financial_exposure, "f"),
        tool_results=all_tool_results,
    )
    messages.append({"role": "user", "content": conclusion_prompt})

    try:
        final_response = provider._client.chat.completions.create(  # type: ignore[union-attr]
            model=provider._model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1024,
        )
        raw    = final_response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as exc:
        logger.error(
            "OpenAI final conclusion call failed for exception %s: %s. "
            "Falling back to mock.", exc_id, exc
        )
        mock_output = _run_mock_investigation(db, exception_record, lifecycle_trace)
        return mock_output, True

    # ── Build InvestigationOutput from parsed JSON ────────────────────────
    confidence = float(parsed.get("confidence", 0.5))
    band       = confidence_to_band(confidence)

    # Validate recommended_action; fall back to investigate_manually if unknown
    raw_action = parsed.get("recommended_action", "investigate_manually")
    try:
        rec_action = RecommendedAction(raw_action)
    except ValueError:
        logger.warning(
            "OpenAI returned unknown recommended_action '%s'; "
            "substituting 'investigate_manually'.", raw_action
        )
        rec_action = RecommendedAction.INVESTIGATE_MANUALLY

    output = InvestigationOutput(
        exception_id=exc_id,
        exception_type=exception_record.exception_type,
        severity=exception_record.severity,
        root_cause=parsed.get("root_cause", ""),
        evidence=parsed.get("evidence", all_tool_results),
        missing_evidence=parsed.get("missing_evidence", []),
        financial_exposure=format(exception_record.financial_exposure, "f"),
        impact_summary=parsed.get("impact_summary", ""),
        confidence=confidence,
        confidence_band=band,
        recommendation=parsed.get("recommendation", ""),
        recommended_action=rec_action,
        requires_human_review=parsed.get("requires_human_review", confidence < 0.90),
        agent_provider="openai",
        tool_calls=tool_calls_executed,
        lifecycle_trace=lifecycle_trace,
    )
    return output, False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_investigation(
    db: Session,
    exception_id: str,
    provider_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Run a full investigation for the given exception_id.

    Flow:
      1. Load exception record.
      2. Build lifecycle trace (always, regardless of provider).
      3. Run OpenAI investigation if provider is available; otherwise mock.
      4. On any OpenAI error, fall back to mock and record the fallback.
      5. Persist investigation + audit trail.

    Returns a dict with keys:
        investigation        – persisted Investigation ORM row
        output               – InvestigationOutput schema
        requires_human_review – bool
        missing_evidence      – list[str]

    Returns None if the exception is not found.
    """
    from sqlalchemy import select
    from app.core.config import get_settings

    settings       = get_settings()
    chosen_provider = provider_name or settings.llm_provider

    exc_record = db.execute(
        select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
    ).scalar_one_or_none()

    if exc_record is None:
        return None

    # Always build lifecycle trace — independent of provider
    trace = build_lifecycle_trace(db, exc_record.transaction_id)

    # Select provider and run investigation
    provider     = get_provider(chosen_provider)
    fallback_used = False

    try:
        if isinstance(provider, OpenAIProvider) and provider.is_available():
            logger.info(
                "Starting OpenAI investigation for exception %s (model=%s)",
                exception_id, provider._model,
            )
            output, fallback_used = _run_openai_investigation(
                db, exc_record, trace, provider
            )
            if fallback_used:
                logger.warning(
                    "OpenAI investigation fell back to mock for exception %s.",
                    exception_id,
                )
        else:
            logger.info(
                "Running mock investigation for exception %s (provider=%s).",
                exception_id, chosen_provider,
            )
            output = _run_mock_investigation(db, exc_record, trace)

    except Exception as exc:
        logger.error(
            "Unexpected error during investigation for exception %s: %s. "
            "Falling back to mock.", exception_id, exc
        )
        output        = _run_mock_investigation(db, exc_record, trace)
        fallback_used = True

    inv = _persist_investigation(db, output, exc_record, fallback_used=fallback_used)
    db.commit()

    return {
        "investigation":        inv,
        "output":               output,
        "requires_human_review": output.requires_human_review,
        "missing_evidence":     output.missing_evidence,
    }
