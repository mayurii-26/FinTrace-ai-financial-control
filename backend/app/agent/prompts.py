"""Prompt templates for the FinTrace AI investigation agent.

All prompts are pure-Python strings — no templating library required.
The system prompt is the agent's permanent instruction set.
The user prompt is built from actual tool-call results for each investigation.

Design principle:  "Deterministic finance. Probabilistic intelligence."
  - The deterministic control engine owns all monetary calculations.
  - The AI agent owns evidence interpretation and recommendation reasoning.
  - Neither overrides the other.
"""
from __future__ import annotations

from typing import Any, Dict

# ---------------------------------------------------------------------------
# System prompt — permanent agent instructions
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the FinTrace Financial Investigation Controller — a specialised AI agent \
built for payment lifecycle reconciliation and financial exception investigation.

Your mandate is to investigate detected financial exceptions by calling the \
provided read-only database tools, interpreting the evidence, and producing a \
structured, evidence-backed investigation conclusion.

=======================================================================
CORE OPERATING PRINCIPLE
=======================================================================
"Deterministic finance. Probabilistic intelligence."

The FinTrace deterministic control engine has already:
  1. Processed every transaction through strict financial rules.
  2. Computed all monetary values (amounts, exposures, discrepancies).
  3. Flagged this exception with a specific type and severity.

You do NOT recalculate, override, or dispute those computed values.
You READ them, INTERPRET them, and EXPLAIN what happened.

=======================================================================
MANDATORY INVESTIGATION PROCEDURE
=======================================================================
1. ALWAYS call get_control_evidence first to understand what the control
   engine found.
2. ALWAYS call get_financial_timeline to see the full lifecycle sequence.
3. Then call additional tools based on the exception type:
   - settlement_amount_discrepancy -> get_settlements, get_payments
   - refund_closure_failure        -> get_refunds, get_settlements
   - duplicate_financial_event     -> get_payments
   - orphan_financial_event        -> get_payments, get_bank_entries
   - missing_downstream_event      -> get_settlements, get_bank_entries
   - settlement_timing_anomaly     -> get_financial_timeline (already called)
4. NEVER form conclusions before calling tools.
5. Cite SPECIFIC values from tool results in your root_cause statement.

=======================================================================
ABSOLUTE PROHIBITIONS
=======================================================================
X  Do NOT calculate, recompute, or modify any monetary amount.
   All financial figures are authoritative outputs of the control engine.
X  Do NOT initiate payments, refunds, settlements, or chargebacks.
   You produce recommendations. A human controller takes action.
X  Do NOT modify database records. All tools are strictly read-only.
X  Do NOT invent financial records that do not exist in tool results.
X  Do NOT fabricate confidence. If evidence is insufficient, say so.
X  Do NOT perform arithmetic on amounts returned by tools.
   Do not compute "10000 - 9750 = 250" — read the pre-computed diff.

=======================================================================
CONFIDENCE RULES (STRICTLY ENFORCED)
=======================================================================
  >= 0.90  ->  high_confidence        Direct action can be recommended.
  0.70-0.89 -> requires_verification  Controller must review before acting.
  < 0.70   ->  insufficient_evidence  Evidence is ambiguous; human review required.

If critical evidence is absent from tool results, set confidence < 0.70
and explicitly list what is missing in missing_evidence.

=======================================================================
INVESTIGATION OUTPUT FORMAT
=======================================================================
Respond ONLY with a valid JSON object (no markdown, no extra text):

{
  "root_cause": "1-2 sentence factual statement citing specific values \
from tool results. Do not invent values.",
  "impact_summary": "Plain-language description of financial consequence. \
Do not compute; read from control_evidence.",
  "evidence": {
    "key_fact_1": "value directly from a tool result",
    "key_fact_2": "value directly from a tool result"
  },
  "missing_evidence": ["list of named data sources that would raise confidence"],
  "confidence": 0.0,
  "recommendation": "2-4 sentence specific next-step guidance for the controller.",
  "recommended_action": "exactly one of: raise_dispute | initiate_clawback | \
refund_duplicate | investigate_manually | escalate_to_gateway | \
monitor_and_escalate | auto_resolve",
  "requires_human_review": true
}

DISTINCTION: facts vs. inference
  - Value is in tool results       -> state as fact.
  - Value is reasoned/inferred     -> qualify ("likely", "suggests").
  - Value is unavailable           -> name in missing_evidence.
"""

# ---------------------------------------------------------------------------
# Tool definitions for OpenAI function/tool calling
# ---------------------------------------------------------------------------

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_transaction",
            "description": (
                "Fetch core transaction fields: status, exception_type, "
                "financial_exposure, ground_truth_type. Confirms the transaction "
                "exists and shows its high-level state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "The transaction ID to look up.",
                    }
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": (
                "Fetch the order record for a transaction: order_id, amount, "
                "timestamp. This is the originating purchase amount before fees."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payments",
            "description": (
                "Fetch all payment records for a transaction. Returns count, "
                "orphan_count, duplicate_detected flag, and per-payment details "
                "(amount, status, is_orphan, timestamp). Essential for "
                "duplicate_financial_event and orphan_financial_event types."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refunds",
            "description": (
                "Fetch all refund records for a transaction, including "
                "total_refund_amount and individual refund details. Essential "
                "for refund_closure_failure investigations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_settlements",
            "description": (
                "Fetch all settlement records. Each record includes "
                "expected_settlement (pre-computed by control engine), "
                "actual_settlement (received from gateway), fee_amount, "
                "tax_amount, and is_orphan. Essential for "
                "settlement_amount_discrepancy and refund_closure_failure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bank_entries",
            "description": (
                "Fetch all bank credit entries for a transaction. Returns "
                "bank_entry_id, settlement_id, amount, is_orphan, timestamp. "
                "Essential for missing_downstream_event and orphan_financial_event."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_timeline",
            "description": (
                "Assemble a chronological financial timeline combining ORDER, "
                "PAYMENT, REFUND, SETTLEMENT, and BANK_CREDIT stages. Includes "
                "timing gaps between consecutive stages in hours. Use this to "
                "understand the full lifecycle sequence and identify where it "
                "broke. Essential for settlement_timing_anomaly investigations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_control_evidence",
            "description": (
                "Fetch the stored control engine evidence for an exception. "
                "Contains pre-computed indicators: settlement_consistency_diff, "
                "amount_integrity_diff, duplicate_details, orphan_details, "
                "missing_stages, settlement_days_late, bank_days_late, "
                "refund_present, lifecycle_completeness_ok. "
                "ALWAYS call this first — it is the authoritative record of "
                "what the deterministic engine found."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "exception_id": {
                        "type": "string",
                        "description": "The exception ID (not the transaction ID).",
                    }
                },
                "required": ["exception_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# User prompt builders
# ---------------------------------------------------------------------------

def build_initial_prompt(
    exception_id: str,
    transaction_id: str,
    exception_type: str,
    severity: str,
    financial_exposure: str,
) -> str:
    """Opening prompt before any tool calls.

    Instructs the agent to follow the mandatory procedure:
    get_control_evidence first, then get_financial_timeline,
    then type-specific tools.
    """
    return (
        "INVESTIGATION REQUEST\n"
        "---------------------\n"
        f"Exception ID  : {exception_id}\n"
        f"Transaction ID: {transaction_id}\n"
        f"Type          : {exception_type}\n"
        f"Severity      : {severity}\n"
        f"Exposure      : {financial_exposure} (pre-computed by control engine)\n"
        "\n"
        "Begin the investigation:\n"
        f"1. Call get_control_evidence with exception_id={exception_id}\n"
        f"2. Call get_financial_timeline with transaction_id={transaction_id}\n"
        f"3. Call additional tools as needed for exception type '{exception_type}'\n"
        "4. After gathering sufficient evidence, produce your JSON conclusion.\n"
        "\n"
        "Do NOT form conclusions before calling tools."
    )


def build_investigation_prompt(
    exception_id: str,
    transaction_id: str,
    exception_type: str,
    severity: str,
    financial_exposure: str,
    tool_results: Dict[str, Any],
) -> str:
    """Final prompt asking the agent to produce its JSON conclusion.

    Called after the tool-calling loop completes. Includes all collected
    tool results so the model can reference values it may not have
    explicitly cited during the loop.
    """
    import json

    return (
        "PRODUCE INVESTIGATION CONCLUSION\n"
        "--------------------------------\n"
        f"Exception ID  : {exception_id}\n"
        f"Transaction ID: {transaction_id}\n"
        f"Type          : {exception_type}\n"
        f"Severity      : {severity}\n"
        f"Exposure      : {financial_exposure} (authoritative — do not recompute)\n"
        "\n"
        "Evidence collected from database tools:\n"
        f"{json.dumps(tool_results, indent=2, default=str)}\n"
        "\n"
        "Using ONLY the evidence above, produce your structured JSON investigation "
        "conclusion. Cite specific values. Do not invent data. No markdown."
    )
