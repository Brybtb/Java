"""Money primitives. The decision path uses ``Decimal`` exclusively: float
addition is non-associative, so summing the same values in a different order can
produce a different result — a silent determinism leak. One rounding policy
lives here and nowhere else.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Any

# Wide enough precision that intermediate products never lose cents; we only
# round at presentation/aggregation boundaries via the helpers below.
getcontext().prec = 34

CENTS = Decimal("0.01")
WHOLE = Decimal("1")


def D(value: Any) -> Decimal:
    """Coerce ints/floats/strings/Decimals to Decimal deterministically.

    Floats are routed through ``str`` so ``0.1`` becomes ``Decimal('0.1')`` and
    not the binary-float tail. ``None``/``""`` become 0.
    """
    if value is None or value == "":
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise TypeError("refusing to treat bool as money")
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def cents(value: Any) -> Decimal:
    """Round to the nearest cent, banker's rounding (stable, unbiased)."""
    return D(value).quantize(CENTS, rounding=ROUND_HALF_EVEN)


def whole(value: Any) -> Decimal:
    """Round to a whole dollar (used for headline figures)."""
    return D(value).quantize(WHOLE, rounding=ROUND_HALF_EVEN)


def total(values) -> Decimal:
    """Sum an iterable in a fixed left-to-right order. Inputs should already be
    ordered by the caller; this never reorders, preserving determinism."""
    acc = Decimal(0)
    for v in values:
        acc += D(v)
    return acc


def pct(value: Any) -> Decimal:
    """Coerce a percentage-as-fraction (e.g. 0.06) to Decimal."""
    return D(value)
