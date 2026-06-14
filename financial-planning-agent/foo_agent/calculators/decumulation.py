"""Decumulation-phase calculators (retirement income). Deterministic.

Covers the steps the accumulation FOO never addressed: taking RMDs, sequencing
withdrawals tax-efficiently, and using low-bracket years to fill with conversions/
withdrawals. The estate/IRMAA nuances are surfaced as guidance, not hard numbers.
"""
from __future__ import annotations

from .context import CalcContext
from .money import D, whole
from .rmd import rmd_summary
from .tax import marginal_rate

_TAX_DEFERRED = ("employer_401k", "ira", "traditional_ira", "403b")
_TAXABLE = ("taxable", "brokerage")
_ROTH = ("roth_ira", "roth_401k")


def _bucket(ctx: CalcContext, keys) -> D:
    accts = ctx.get("accounts", {}) or {}
    return sum((D(accts[k]["balance"]) for k in keys
               if isinstance(accts.get(k), dict) and "balance" in accts[k]), D(0))


def rmd_due(ctx: CalcContext) -> dict:
    age = ctx.age()
    birth_year = ctx.as_of.year - age if age else None
    return rmd_summary(age, _bucket(ctx, _TAX_DEFERRED), birth_year)


def drawdown_order(ctx: CalcContext) -> dict:
    """Recommended tax-efficient drawdown order + current bucket balances."""
    return {
        "recommended_order": ["taxable", "tax_deferred", "roth"],
        "taxable": str(whole(_bucket(ctx, _TAXABLE))),
        "tax_deferred": str(whole(_bucket(ctx, _TAX_DEFERRED))),
        "roth": str(whole(_bucket(ctx, _ROTH))),
        "note": "Spend taxable first to let tax-advantaged accounts compound; Roth "
                "last. RMDs (if active) must be satisfied from tax-deferred regardless.",
    }


def bracket_fill(ctx: CalcContext) -> dict:
    """Headroom to the top of the current bracket — the room to realize income
    (Roth conversions / capital gains) at the current marginal rate."""
    mr = marginal_rate(ctx)
    return {
        "taxable_income": mr["taxable_income"],
        "marginal_rate": mr["marginal_rate"],
        "current_bracket_top": mr["current_bracket_top"],
        "bracket_headroom": mr["bracket_headroom"],
        "note": "Low-bracket retirement years before RMDs/Social Security begin are "
                "prime for Roth conversions or 0%-capital-gains harvesting; watch IRMAA.",
    }
