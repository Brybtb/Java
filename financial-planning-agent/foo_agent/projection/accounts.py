"""Translate a profile + CMA into the inputs the projection/Monte Carlo engines
need. Investable assets, annual savings, and the retirement spending target are
derived deterministically from the profile."""
from __future__ import annotations

from dataclasses import dataclass

from ..calculators.money import D
from ..montecarlo.cma import CMA

# Account keys treated as investable (vs. emergency cash).
INVESTABLE = ("employer_401k", "roth_ira", "hsa", "taxable", "ira", "brokerage")


@dataclass(frozen=True)
class PlanInputs:
    start_age: int
    retire_age: int
    end_age: int
    initial_balance: float
    annual_contribution: float
    annual_spend_retire: float  # nominal at retirement year
    inflation: float
    mean_return: float
    stdev: float


def _investable_total(profile: dict) -> float:
    accounts = profile.get("accounts", {}) or {}
    total = D(0)
    for key in INVESTABLE:
        acct = accounts.get(key)
        if isinstance(acct, dict):
            total += D(acct.get("balance", 0))
    return float(total)


def _annual_contribution(profile: dict) -> float:
    gross = D(profile.get("income", {}).get("gross_annual", 0))
    contrib = profile.get("contributions", {}) or {}
    accts = profile.get("accounts", {}) or {}
    deferral_pct = D(contrib.get("employer_401k", {}).get("pct", 0))
    deferral = gross * deferral_pct
    match_rate = D(accts.get("employer_401k", {}).get("match_rate", 0))
    match_cap = D(accts.get("employer_401k", {}).get("match_pct_cap", 0))
    captured = deferral_pct if deferral_pct < match_cap else match_cap
    match = gross * captured * match_rate
    roth = D(contrib.get("roth_ira", {}).get("annual", 0))
    hsa = D(contrib.get("hsa", {}).get("annual", 0))
    return float(deferral + match + roth + hsa)


def build_plan_inputs(profile: dict, cma: CMA) -> PlanInputs:
    start_age = int(profile.get("household", {}).get("primary_age", 0) or 0)
    retire_age = cma.default_retirement_age
    for g in profile.get("goals", []) or []:
        if g.get("type") == "retirement" and g.get("target_age"):
            retire_age = int(g["target_age"])
            break
    retire_age = max(retire_age, start_age + 1)

    expenses = profile.get("expenses", {}) or {}
    monthly = D(expenses.get("monthly_total", expenses.get("monthly_essential", 0)))
    spend_today = monthly * 12 * D(str(cma.spending_replacement))
    years_to_retire = retire_age - start_age
    # Inflate today's spending need to the retirement year (nominal).
    spend_retire = float(spend_today * (D(1) + D(str(cma.inflation))) ** years_to_retire)

    return PlanInputs(
        start_age=start_age,
        retire_age=retire_age,
        end_age=cma.longevity_age,
        initial_balance=_investable_total(profile),
        annual_contribution=_annual_contribution(profile),
        annual_spend_retire=spend_retire,
        inflation=cma.inflation,
        mean_return=cma.mean_return,
        stdev=cma.stdev,
    )
