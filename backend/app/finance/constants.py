"""Deterministic financial constants used by the control engine and the
rule-based anomaly classifier. These values are intentionally explicit and
version-controlled so every benchmark run is reproducible - the LLM never
sees or influences any of these numbers.
"""
from __future__ import annotations

from decimal import Decimal

# Rounding precision applied to every monetary comparison.
CENT = Decimal("0.01")

# Tolerance below which two monetary values are considered "equal" (covers
# floating/rounding noise introduced by realistic fee/tax computations).
AMOUNT_TOLERANCE = Decimal("0.01")

# Service Level Agreement windows for the settlement lifecycle. Breaching
# these deterministically flags a "settlement_timing_anomaly".
SETTLEMENT_SLA_DAYS = 3
BANK_CREDIT_SLA_DAYS = 2

# Typical Razorpay-style payment gateway economics used by the synthetic
# data generator (also referenced by the control engine when recomputing
# the *expected* settlement amount).
DEFAULT_FEE_RATE = Decimal("0.02")     # 2% platform fee
DEFAULT_TAX_RATE = Decimal("0.18")     # 18% GST on the fee

# Below this exposure, an otherwise-clean auto-resolvable exception can be
# closed automatically without human controller review.
AUTO_RESOLVE_EXPOSURE_CEILING = Decimal("500.00")

# Severity thresholds (INR) - primarily driven by financial exposure.
SEVERITY_CRITICAL_THRESHOLD = Decimal("50000.00")
SEVERITY_HIGH_THRESHOLD = Decimal("10000.00")
SEVERITY_MEDIUM_THRESHOLD = Decimal("1000.00")

# Minimum severity floor enforced for structurally important control
# breaks, regardless of the raw exposure amount, because they indicate a
# broken process rather than a pure amount mismatch.
CONTROL_IMPORTANCE_FLOOR = {
    "duplicate_financial_event": "medium",
    "orphan_financial_event": "medium",
    "refund_closure_failure": "medium",
    "missing_downstream_event": "medium",
}

# Priority order used by the classifier when a transaction trips more than
# one control check at once - the highest-priority (first) match wins and
# becomes the single reported ``exception_type``.
EXCEPTION_PRIORITY = [
    "duplicate_financial_event",
    "orphan_financial_event",
    "refund_closure_failure",
    "missing_downstream_event",
    "settlement_amount_discrepancy",
    "settlement_timing_anomaly",
]
