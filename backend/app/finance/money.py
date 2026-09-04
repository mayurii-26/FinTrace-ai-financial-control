"""Decimal-only monetary helpers.

FINANCIAL RULE: every monetary computation in FinTrace flows through this
module (or uses ``decimal.Decimal`` directly). Floats are never used for
money and the AI/LLM layer never performs or overrides an arithmetic
calculation - it only reasons over numbers that were already computed here.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable, Optional, Union

from app.finance.constants import CENT

Numeric = Union[Decimal, int, float, str, None]


def to_decimal(value: Numeric) -> Decimal:
    """Safely coerce any numeric-ish input into a quantized Decimal."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            d = Decimal("0.00")
    return quantize(d)


def quantize(value: Decimal) -> Decimal:
    """Round to 2 decimal places using banker-safe HALF_UP rounding."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def sum_decimals(values: Iterable[Numeric]) -> Decimal:
    total = Decimal("0.00")
    for v in values:
        total += to_decimal(v)
    return quantize(total)


def abs_diff(a: Numeric, b: Numeric) -> Decimal:
    return quantize(abs(to_decimal(a) - to_decimal(b)))


def within_tolerance(a: Numeric, b: Numeric, tolerance: Optional[Decimal] = None) -> bool:
    from app.finance.constants import AMOUNT_TOLERANCE

    tol = tolerance if tolerance is not None else AMOUNT_TOLERANCE
    return abs_diff(a, b) <= tol
