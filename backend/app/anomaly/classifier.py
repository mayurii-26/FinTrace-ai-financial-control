"""Rule-based, deterministic exception classifier.

Maps a ``ControlResult`` onto a single ``exception_type`` (or ``None`` for
a healthy transaction) using the fixed priority order defined in
``app.finance.constants.EXCEPTION_PRIORITY``. This is plain Python
if/elif logic - no ML, no LLM - so classification is 100% reproducible
and auditable.
"""
from __future__ import annotations

from typing import Optional

from app.finance.control_engine import ControlResult


def classify_exception(control: ControlResult) -> Optional[str]:
    """Return the single highest-priority exception_type tripped by the
    control result, or ``None`` if the transaction is fully healthy."""

    if control.duplicate_detected:
        return "duplicate_financial_event"

    if control.orphan_detected:
        return "orphan_financial_event"

    if control.refund_present and not control.refund_consistency_ok:
        return "refund_closure_failure"

    if not control.lifecycle_completeness_ok:
        missing = set(control.missing_stages)
        if "settlement" in missing or "bank_entry" in missing:
            return "missing_downstream_event"

    if not control.settlement_consistency_ok:
        return "settlement_amount_discrepancy"

    if not control.settlement_timing_ok:
        return "settlement_timing_anomaly"

    return None
