"""Deterministic severity classification.

Severity is derived primarily from financial exposure (a Decimal amount
computed by the control engine) with a control-importance floor applied
for structurally significant breaks. The AI agent never sets severity.
"""
from __future__ import annotations

from decimal import Decimal

from app.finance.constants import (
    CONTROL_IMPORTANCE_FLOOR,
    SEVERITY_CRITICAL_THRESHOLD,
    SEVERITY_HIGH_THRESHOLD,
    SEVERITY_MEDIUM_THRESHOLD,
)

_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _exposure_severity(exposure: Decimal) -> str:
    if exposure >= SEVERITY_CRITICAL_THRESHOLD:
        return "critical"
    if exposure >= SEVERITY_HIGH_THRESHOLD:
        return "high"
    if exposure >= SEVERITY_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def classify_severity(exception_type: str, financial_exposure: Decimal) -> str:
    """Return one of low/medium/high/critical for a given exception."""
    base = _exposure_severity(financial_exposure)
    floor = CONTROL_IMPORTANCE_FLOOR.get(exception_type)
    if floor and _RANK[floor] > _RANK[base]:
        return floor
    return base
