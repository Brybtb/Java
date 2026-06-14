"""Deterministic tax-efficient withdrawal plan. Buckets the household's accounts
into taxable / tax-deferred / Roth and recommends a first-year draw using the
conventional order (taxable first to let tax-advantaged accounts keep
compounding, Roth last). Builds on projection/withdrawal.split_withdrawal."""
from __future__ import annotations

from ..calculators.money import D, cents
from ..projection.withdrawal import DEFAULT_ORDER, split_withdrawal

_BUCKET_MAP = {
    "taxable": ("taxable", "brokerage"),
    "tax_deferred": ("employer_401k", "ira", "traditional_ira", "403b"),
    "roth": ("roth_ira", "roth_401k"),
}


def _buckets(profile: dict) -> dict:
    accts = profile.get("accounts", {}) or {}
    out = {}
    for bucket, keys in _BUCKET_MAP.items():
        total = D(0)
        for k in keys:
            a = accts.get(k)
            if isinstance(a, dict):
                total += D(a.get("balance", 0))
        out[bucket] = total
    return out


def withdrawal_plan(profile: dict, annual_need=None) -> dict:
    buckets = _buckets(profile)
    if annual_need is None:
        exp = profile.get("expenses", {}) or {}
        annual_need = D(exp.get("monthly_total", exp.get("monthly_essential", 0))) * 12
    split = split_withdrawal(annual_need, {k: str(v) for k, v in buckets.items()})
    return {
        "order": list(DEFAULT_ORDER),
        "annual_need": str(cents(annual_need)),
        "buckets": {k: str(cents(v)) for k, v in buckets.items()},
        "first_year_draw": split["draws"],
        "shortfall": split["shortfall"],
        "note": "Taxable first, Roth last. Required Minimum Distributions (age 73+) "
                "may force tax-deferred withdrawals earlier; model in Phase 3.",
        "citation": "tax-efficient withdrawal sequencing guidance",
    }
