"""Deterministic single-path projection (Decimal, exact). Uses the CMA mean
return — no randomness — so it is byte-stable and golden-testable. The Monte
Carlo module re-runs the same mechanics over sampled return sequences."""
from __future__ import annotations

from ..calculators.money import D, whole
from .accounts import PlanInputs


def project_deterministic(pi: PlanInputs) -> dict:
    bal = D(str(pi.initial_balance))
    contribution = D(str(pi.annual_contribution))
    infl = D(str(pi.inflation))
    r = D(str(pi.mean_return))
    spend0 = D(str(pi.annual_spend_retire))

    ss0 = D(str(pi.ss_annual))           # today's-dollar SS benefit at claim age
    tax_rate = D(str(pi.retirement_tax_rate))

    path = []
    balance_at_retirement = None
    depleted_age = None

    for age in range(pi.start_age, pi.end_age):
        if age < pi.retire_age:
            bal = bal * (D(1) + r) + contribution
            contribution = contribution * (D(1) + infl)
        else:
            years_since_start = age - pi.start_age
            spend = spend0 * (D(1) + infl) ** (age - pi.retire_age)
            # C6: Social Security offsets the spending need once claimed; the
            # portfolio covers the gap, grossed up for a blended tax rate.
            ss = (ss0 * (D(1) + infl) ** years_since_start) if (pi.ss_claim_age and age >= pi.ss_claim_age) else D(0)
            net_need = spend - ss
            if net_need < 0:
                net_need = D(0)
            gross_draw = net_need / (D(1) - tax_rate) if tax_rate < 1 else net_need
            bal = bal * (D(1) + r) - gross_draw
            if bal < 0:
                bal = D(0)
                if depleted_age is None:
                    depleted_age = age + 1
        end_age_year = age + 1
        if end_age_year == pi.retire_age:
            balance_at_retirement = bal
        path.append({"age": end_age_year, "balance": str(whole(bal))})

    if balance_at_retirement is None:
        balance_at_retirement = bal  # already retired at start

    # 4%-rule nest-egg target at retirement (25x first-year retirement spend).
    target_nest_egg = spend0 * D(25)
    funded_ratio = (
        (balance_at_retirement / target_nest_egg) if target_nest_egg > 0 else D(0)
    )

    return {
        "start_age": pi.start_age,
        "retire_age": pi.retire_age,
        "end_age": pi.end_age,
        "initial_balance": str(whole(pi.initial_balance)),
        "annual_contribution": str(whole(pi.annual_contribution)),
        "annual_spend_retire": str(whole(pi.annual_spend_retire)),
        "balance_at_retirement": str(whole(balance_at_retirement)),
        "ending_balance": str(whole(bal)),
        "target_nest_egg": str(whole(target_nest_egg)),
        "funded_ratio": str(funded_ratio.quantize(D("0.001"))),
        "depleted_age": depleted_age,
        "success": depleted_age is None,
        "path": path,
    }
