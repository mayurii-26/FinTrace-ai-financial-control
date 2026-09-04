"""Benchmark runner for the FinTrace deterministic control engine.

Runs the control engine over every transaction in the database, compares
detected exception_type against ground_truth_type, and computes
precision / recall / F1 / throughput and financial statistics.

The benchmark is always computed from live database data (not cached) so
every call reflects the current state of the evaluated transactions.
"""
from __future__ import annotations

import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.finance.control_engine import run_controls
from app.finance.exposure import compute_financial_exposure
from app.finance.lifecycle_builder import build_bundle
from app.anomaly.classifier import classify_exception
from app.models.exception import ExceptionRecord, ExceptionStatus
from app.models.transaction import Transaction, TransactionStatus


def _load_transactions(db: Session) -> List[Transaction]:
    """Load all transactions with their relationships eagerly."""
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select

    stmt = (
        select(Transaction)
        .options(
            selectinload(Transaction.order),
            selectinload(Transaction.payments),
            selectinload(Transaction.refunds),
            selectinload(Transaction.settlements),
            selectinload(Transaction.bank_entries),
        )
    )
    return list(db.execute(stmt).scalars().all())


def run_benchmark(db: Session) -> Dict[str, Any]:
    """Execute a full benchmark pass and return a result dict matching
    ``BenchmarkResponseSchema``.

    Throughput is measured using wall-clock time over the evaluation loop
    only (DB load time excluded so we measure engine speed, not I/O).
    """
    transactions = _load_transactions(db)
    total = len(transactions)

    if total == 0:
        return _empty_result()

    # ---------- financial totals from order amounts ----------
    total_financial_value = Decimal("0.00")
    for txn in transactions:
        if txn.order:
            total_financial_value += txn.order.amount

    # ---------- evaluation loop (timed) ----------
    tp = 0  # correctly detected anomaly
    fp = 0  # engine says anomaly, ground truth says healthy
    fn = 0  # engine says healthy, ground truth says anomaly
    tn = 0  # both say healthy
    total_exposure = Decimal("0.00")
    per_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})

    t_start = time.perf_counter()

    for txn in transactions:
        bundle = build_bundle(txn)
        control = run_controls(bundle)
        detected_type = classify_exception(control)
        exposure = compute_financial_exposure(bundle, control, detected_type)
        total_exposure += exposure

        gt_is_anomaly = txn.ground_truth_is_anomaly
        detected_is_anomaly = detected_type is not None
        gt_type = txn.ground_truth_type

        if gt_is_anomaly and detected_is_anomaly:
            tp += 1
            per_type[gt_type]["tp"] += 1
        elif not gt_is_anomaly and detected_is_anomaly:
            fp += 1
            per_type[gt_type]["fp"] += 1
        elif gt_is_anomaly and not detected_is_anomaly:
            fn += 1
            per_type[gt_type]["fn"] += 1
        else:
            tn += 1
            per_type[gt_type]["tn"] += 1

    duration = time.perf_counter() - t_start
    throughput = total / duration if duration > 0 else 0.0

    # ---------- precision / recall / F1 ----------
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    correct = tp + tn
    match_rate = correct / total if total > 0 else 0.0

    # ---------- exception status counts from DB ----------
    from sqlalchemy import func, select

    status_counts = dict(
        db.execute(
            select(ExceptionRecord.status, func.count(ExceptionRecord.exception_id))
            .group_by(ExceptionRecord.status)
        ).all()
    )

    # ---------- per-type breakdown ----------
    per_type_stats = []
    for exc_type, counts in sorted(per_type.items()):
        t_tp = counts["tp"]
        t_fp = counts["fp"]
        t_fn = counts["fn"]
        t_tn = counts["tn"]
        t_prec = t_tp / (t_tp + t_fp) if (t_tp + t_fp) > 0 else 0.0
        t_rec = t_tp / (t_tp + t_fn) if (t_tp + t_fn) > 0 else 0.0
        t_f1 = (
            2 * t_prec * t_rec / (t_prec + t_rec)
            if (t_prec + t_rec) > 0
            else 0.0
        )
        per_type_stats.append({
            "exception_type": exc_type,
            "tp": t_tp,
            "fp": t_fp,
            "fn": t_fn,
            "tn": t_tn,
            "precision": round(t_prec, 4),
            "recall": round(t_rec, 4),
            "f1_score": round(t_f1, 4),
        })

    healthy_count = tn + fp  # ground-truth healthy
    exception_count = tp + fn  # ground-truth anomaly

    return {
        "total_records": total,
        "healthy_count": healthy_count,
        "exception_count": exception_count,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "match_rate_pct": round(match_rate * 100, 2),
        "total_financial_value": format(total_financial_value, "f"),
        "total_financial_exposure": format(total_exposure, "f"),
        "open_exceptions": status_counts.get(ExceptionStatus.OPEN, 0),
        "auto_resolved_exceptions": status_counts.get(ExceptionStatus.AUTO_RESOLVED, 0),
        "approved_exceptions": status_counts.get(ExceptionStatus.APPROVED, 0),
        "rejected_exceptions": status_counts.get(ExceptionStatus.REJECTED, 0),
        "throughput_records_per_sec": round(throughput, 2),
        "duration_seconds": round(duration, 4),
        "per_type_stats": per_type_stats,
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "total_records": 0,
        "healthy_count": 0,
        "exception_count": 0,
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "true_negatives": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1_score": 0.0,
        "match_rate_pct": 0.0,
        "total_financial_value": "0.00",
        "total_financial_exposure": "0.00",
        "open_exceptions": 0,
        "auto_resolved_exceptions": 0,
        "approved_exceptions": 0,
        "rejected_exceptions": 0,
        "throughput_records_per_sec": 0.0,
        "duration_seconds": 0.0,
        "per_type_stats": [],
    }
