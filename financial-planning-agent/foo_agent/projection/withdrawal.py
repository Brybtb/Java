"""Tax-aware withdrawal sequencing. The conventional default order spends taxable
first (lets tax-advantaged accounts keep compounding), then tax-deferred, then
Roth last. Exposed as a pure helper so the Phase-2 tax module can refine it; the
Phase-1 success metric only needs total portfolio longevity."""
from __future__ import annotations

from ..calculators.money import D, cents

DEFAULT_ORDER = ("taxable", "tax_deferred", "roth")


def split_withdrawal(amount, buckets: dict, order=DEFAULT_ORDER) -> dict:
    """Draw ``amount`` from buckets in ``order``. Returns per-bucket draws and any
    unmet shortfall. Deterministic: fixed order, Decimal math."""
    remaining = D(amount)
    draws = {}
    for name in order:
        avail = D(buckets.get(name, 0))
        take = avail if avail < remaining else remaining
        if take < 0:
            take = D(0)
        draws[name] = str(cents(take))
        remaining -= take
        if remaining <= 0:
            remaining = D(0)
            break
    return {"draws": draws, "shortfall": str(cents(remaining))}
