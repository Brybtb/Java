"""Deterministic Roth-conversion / bracket-fill optimizer (RightCapital /
Holistiplan style). Computes how much ordinary income (e.g. a Roth conversion)
can be recognized to fill to the top of the current and the next ordinary-income
brackets, with the incremental federal tax cost and blended rate for each.
"""
from __future__ import annotations

from ..calculators.context import CalcContext
from ..calculators.money import D, cents
from ..calculators.tax import _ordered_brackets


def _tax_on(taxable: D, brackets: list) -> D:
    owed, lower = D(0), D(0)
    for b in brackets:
        up = b.get("up_to")
        top = D("Infinity") if up is None else D(up)
        rate = D(b.get("rate", 0))
        if taxable > lower:
            owed += (min(taxable, top) - lower) * rate
        lower = top
        if top == D("Infinity"):
            break
    return owed


def conversion_analysis(profile: dict, params: dict, as_of) -> dict:
    ctx = CalcContext(profile=profile, params=params, as_of=as_of)
    filing = ctx.get("household.filing_status", "single")
    gross = D(ctx.get("income.gross_annual", 0))
    std = D(ctx.param(f"tax.standard_deduction.{filing}", 0))
    taxable = gross - std
    if taxable < 0:
        taxable = D(0)

    brackets = _ordered_brackets(ctx.param(f"tax.brackets.{filing}", []) or [])
    base_tax = _tax_on(taxable, brackets)

    # Ceilings strictly above current taxable income become fill targets.
    targets = []
    for b in brackets:
        up = b.get("up_to")
        if up is None:
            continue
        ceiling = D(up)
        if ceiling <= taxable:
            continue
        room = ceiling - taxable
        inc_tax = _tax_on(taxable + room, brackets) - base_tax
        blended = (inc_tax / room) if room > 0 else D(0)
        targets.append({
            "fill_to_bracket_below_rate": str(D(b["rate"])),
            "ceiling": str(cents(ceiling)),
            "conversion_room": str(cents(room)),
            "incremental_tax": str(cents(inc_tax)),
            "blended_rate": str(blended.quantize(D("0.0001"))),
        })

    return {
        "filing_status": filing,
        "taxable_income": str(cents(taxable)),
        "current_marginal_rate": targets[0]["fill_to_bracket_below_rate"] if targets else "0.37",
        "fill_targets": targets[:3],   # current + next two brackets
        "note": "Conversion room fills to the top of each bracket; recognized income "
                "may affect IRMAA, ACA subsidies, and capital-gains stacking — review.",
        "citation": "IRS ordinary-income brackets; Roth conversion guidance",
    }
