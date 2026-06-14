"""Deterministic Social Security claiming optimizer.

Given the Primary Insurance Amount (PIA, the monthly benefit at Full Retirement
Age) and the FRA, computes the benefit at every claiming age 62-70 using SSA's
actuarial rules, the cumulative lifetime benefit to a longevity age, the
utility-maximizing claiming age, and the break-even age vs. claiming at 62.

SSA rules encoded (deterministic, no clock):
  * Early: first 36 months before FRA reduce 5/9 of 1% per month; each additional
    month reduces 5/12 of 1% per month.
  * Delayed: 2/3 of 1% per month (8%/yr) from FRA to age 70; none after 70.
Reference: SSA "Early or Late Retirement" and "Delayed Retirement Credits".
"""
from __future__ import annotations

from ..calculators.money import D, cents

EARLY_FIRST36_PER_MONTH = D("1") / D("180")   # 5/9 of 1% = 1/180
EARLY_BEYOND_PER_MONTH = D("1") / D("240")    # 5/12 of 1% = 1/240
DELAYED_PER_MONTH = D("2") / D("3") / D("100")  # 2/3 of 1% per month


def _factor(claim_age_months: int, fra_months: int) -> D:
    """Benefit multiplier applied to PIA for a given claiming age (in months)."""
    if claim_age_months < fra_months:
        early = fra_months - claim_age_months
        first = min(early, 36)
        beyond = max(early - 36, 0)
        reduction = first * EARLY_FIRST36_PER_MONTH + beyond * EARLY_BEYOND_PER_MONTH
        return D(1) - reduction
    delayed_months = min(claim_age_months - fra_months, (70 * 12) - fra_months)
    delayed_months = max(delayed_months, 0)
    return D(1) + delayed_months * DELAYED_PER_MONTH


def claiming_analysis(pia_monthly, fra_age: float = 67.0, longevity_age: int = 90) -> dict:
    pia = D(pia_monthly)
    fra_months = int(round(fra_age * 12))
    rows = []
    for age in range(62, 71):
        f = _factor(age * 12, fra_months)
        monthly = pia * f
        annual = monthly * 12
        months_collecting = max((longevity_age - age) * 12, 0)
        lifetime = monthly * months_collecting
        rows.append({
            "claim_age": age,
            "factor": str(f.quantize(D("0.0001"))),
            "monthly": str(cents(monthly)),
            "annual": str(cents(annual)),
            "lifetime_to_longevity": str(cents(lifetime)),
            "_lifetime": lifetime,
            "_annual": annual,
        })

    best = max(rows, key=lambda r: (r["_lifetime"], -r["claim_age"]))
    base = rows[0]  # claim at 62

    # Break-even age vs claiming at 62, for the recommended age (first age where
    # cumulative benefit of waiting overtakes claiming at 62).
    breakeven = None
    if best["claim_age"] != 62:
        b_annual, e_annual = base["_annual"], best["_annual"]
        e_start = best["claim_age"]
        for test_age in range(e_start, longevity_age + 1):
            months_b = (test_age - 62) * 12
            months_e = (test_age - e_start) * 12
            cum_b = base["_annual"] / 12 * months_b
            cum_e = best["_annual"] / 12 * months_e
            if cum_e >= cum_b:
                breakeven = test_age
                break

    for r in rows:
        r.pop("_lifetime", None)
        r.pop("_annual", None)

    return {
        "pia_monthly": str(cents(pia)),
        "fra_age": fra_age,
        "longevity_age": longevity_age,
        "by_claim_age": rows,
        "recommended_claim_age": best["claim_age"],
        "recommended_basis": "maximizes cumulative lifetime benefit to longevity age",
        "breakeven_age_vs_62": breakeven,
        "survivor_note": "For married couples, the survivor keeps the larger of the two "
                         "benefits — delaying the higher earner's claim also raises the "
                         "survivor benefit. Spousal/survivor optimization is modeled "
                         "at the household level (joint-life horizon).",
        "citation": "SSA early/late retirement & delayed retirement credit rules",
    }
