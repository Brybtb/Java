"""Protection / risk-management heuristics for the band-900 step: rough life and
disability coverage targets and an estate-document checklist. Deliberately
conservative, advisor-reviewed defaults — not a substitute for an insurance needs
analysis (that arrives with the Phase-3 insurance module)."""
from __future__ import annotations

from .context import CalcContext
from .money import cents, D


def review(ctx: CalcContext) -> dict:
    gross = D(ctx.get("income.gross_annual", 0))
    life_multiple = D(ctx.param("protection.life_income_multiple", 10))
    has_dependents = bool(ctx.get("household.has_dependents", False))

    life_target = gross * life_multiple if has_dependents else gross * D(0)
    checklist = ["will", "durable_power_of_attorney", "healthcare_directive", "beneficiary_review"]
    if bool(ctx.param("state.estate_or_inheritance_tax", False)):
        checklist.append("state_estate_tax_review")
    if bool(ctx.param("state.community_property", False)):
        checklist.append("community_property_titling_review")

    return {
        "suggested_life_coverage": str(cents(life_target)),
        "life_income_multiple": str(life_multiple),
        "has_dependents": has_dependents,
        "disability_note": "Confirm long-term disability covers ~60% of gross income.",
        "estate_checklist": checklist,
    }
