"""Ground-truth taxonomy for the synthetic dataset.

Every generated transaction is stamped with exactly one ``GroundTruthType``
at creation time. This label is stored on the ``Transaction`` row
(``ground_truth_type`` / ``ground_truth_is_anomaly``) purely for later
benchmark evaluation - it is never read by the control engine or the AI
agent while they process a transaction.
"""
from __future__ import annotations

import enum


class GroundTruthType(str, enum.Enum):
    HEALTHY = "healthy"
    SETTLEMENT_AMOUNT_DISCREPANCY = "settlement_amount_discrepancy"
    REFUND_CLOSURE_FAILURE = "refund_closure_failure"
    DUPLICATE_FINANCIAL_EVENT = "duplicate_financial_event"
    ORPHAN_FINANCIAL_EVENT = "orphan_financial_event"
    SETTLEMENT_TIMING_ANOMALY = "settlement_timing_anomaly"
    MISSING_DOWNSTREAM_EVENT = "missing_downstream_event"


# Target distribution used by the synthetic generator. Kept deliberately
# skewed towards "healthy" (as any real payments ledger would be) while
# still guaranteeing a meaningful, non-trivial count of every anomaly
# scenario so precision/recall are statistically legitimate.
GROUND_TRUTH_WEIGHTS: dict[GroundTruthType, float] = {
    GroundTruthType.HEALTHY: 0.55,
    GroundTruthType.SETTLEMENT_AMOUNT_DISCREPANCY: 0.09,
    GroundTruthType.REFUND_CLOSURE_FAILURE: 0.09,
    GroundTruthType.DUPLICATE_FINANCIAL_EVENT: 0.08,
    GroundTruthType.ORPHAN_FINANCIAL_EVENT: 0.08,
    GroundTruthType.SETTLEMENT_TIMING_ANOMALY: 0.08,
    GroundTruthType.MISSING_DOWNSTREAM_EVENT: 0.03,
}

ANOMALY_TYPES = [t for t in GroundTruthType if t != GroundTruthType.HEALTHY]


def is_anomaly(ground_truth_type: str) -> bool:
    return ground_truth_type != GroundTruthType.HEALTHY.value
