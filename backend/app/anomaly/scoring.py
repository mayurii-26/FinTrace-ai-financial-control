"""Supplementary ML anomaly scoring.

This module is intentionally *advisory only*: it uses scikit-learn's
IsolationForest to produce a 0-1 "unusualness" score over engineered,
already-deterministically-computed numeric features (amount diffs, day
deltas, event counts). The score is attached to an exception's evidence
for the AI agent/controller to read as extra context - it never decides
the exception_type, the financial_exposure or the severity. Those are
always produced by the deterministic control engine (see
``app.finance.control_engine``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_NAMES = [
    "amount_integrity_diff",
    "settlement_diff",
    "settlement_days_late",
    "bank_days_late",
    "duplicate_count",
    "orphan_count",
    "refund_ratio",
]


@dataclass
class AnomalyScoringResult:
    scores: Dict[str, float]  # transaction_id -> score in [0, 1]


def compute_anomaly_scores(feature_rows: List[dict]) -> AnomalyScoringResult:
    """Fit an IsolationForest over the batch's engineered features and
    return a normalized 0-1 anomaly score per transaction_id.

    ``feature_rows`` items must contain a ``transaction_id`` key plus the
    numeric keys listed in ``FEATURE_NAMES`` (missing keys default to 0).
    """
    if not feature_rows:
        return AnomalyScoringResult(scores={})

    ids = [row["transaction_id"] for row in feature_rows]
    matrix = np.array(
        [[float(row.get(name, 0.0) or 0.0) for name in FEATURE_NAMES] for row in feature_rows],
        dtype=float,
    )

    # IsolationForest needs at least 2 samples; degrade gracefully for
    # tiny batches (e.g. single-transaction API calls / unit tests).
    if matrix.shape[0] < 8:
        return AnomalyScoringResult(scores={tid: 0.0 for tid in ids})

    model = IsolationForest(
        n_estimators=150,
        contamination="auto",
        random_state=42,
    )
    model.fit(matrix)
    # decision_function: higher = more normal. Invert + min-max normalize
    # so the reported score is intuitive: higher = more anomalous.
    raw = -model.decision_function(matrix)
    lo, hi = float(raw.min()), float(raw.max())
    if hi - lo < 1e-9:
        normalized = np.zeros_like(raw)
    else:
        normalized = (raw - lo) / (hi - lo)

    return AnomalyScoringResult(scores={tid: round(float(s), 4) for tid, s in zip(ids, normalized)})
