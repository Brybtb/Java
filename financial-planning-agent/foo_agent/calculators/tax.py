"""Deterministic marginal/effective federal tax estimation from parameterized
brackets. Used by the projection engine and the insights generator (e.g. to size
a Roth-conversion headroom to the top of a bracket)."""
from __future__ import annotations

from .context import CalcContext
from .money import cents, D


def _ordered_brackets(brackets):
    # Each bracket: {"up_to": number|null, "rate": fraction}. None == infinity.
    def key(b):
        up = b.get("up_to")
        return (D("Infinity") if up is None else D(up))

    return sorted(brackets, key=key)


def marginal_rate(ctx: CalcContext) -> dict:
    filing = ctx.get("household.filing_status", "single")
    gross = D(ctx.get("income.gross_annual", 0))
    std = D(ctx.param(f"tax.standard_deduction.{filing}", 0))
    taxable = gross - std
    if taxable < 0:
        taxable = D(0)

    brackets = ctx.param(f"tax.brackets.{filing}", []) or []
    brackets = _ordered_brackets(brackets)

    tax_owed = D(0)
    lower = D(0)
    marginal = D(0)
    bracket_top = None
    for b in brackets:
        up = b.get("up_to")
        top = D("Infinity") if up is None else D(up)
        rate = D(b.get("rate", 0))
        if taxable > lower:
            span = (min(taxable, top) - lower)
            tax_owed += span * rate
            marginal = rate
            if taxable <= top:
                bracket_top = None if up is None else str(cents(top))
        lower = top
        if top == D("Infinity"):
            break

    effective = (tax_owed / taxable) if taxable > 0 else D(0)
    headroom = None
    if bracket_top is not None:
        headroom = str(cents(D(bracket_top) - taxable))

    return {
        "filing_status": filing,
        "taxable_income": str(cents(taxable)),
        "marginal_rate": str(marginal),
        "effective_rate": str(effective.quantize(D("0.0001"))),
        "estimated_tax": str(cents(tax_owed)),
        "current_bracket_top": bracket_top,
        "bracket_headroom": headroom,
    }
