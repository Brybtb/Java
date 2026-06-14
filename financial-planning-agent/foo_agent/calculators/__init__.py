"""Calculator registry. Rules reference a calculator by its ``module.func``
name in their ``action.calculator`` field; the evaluator dispatches here. The
registry is built once at import and is immutable thereafter.
"""
from __future__ import annotations

from typing import Callable

from .context import CalcContext
from . import contributions, debt, emergency_fund, employer_match, protection, tax

# name -> pure function(CalcContext) -> dict
CALCULATORS: dict[str, Callable[[CalcContext], dict]] = {
    "emergency_fund.starter": emergency_fund.starter,
    "emergency_fund.full": emergency_fund.full,
    "employer_match.capture_full": employer_match.capture_full,
    "debt.high_interest": debt.high_interest,
    "contributions.hsa_max": contributions.hsa_max,
    "contributions.ira_max": contributions.ira_max,
    "contributions.employer_plan_max": contributions.employer_plan_max,
    "contributions.taxable_brokerage": contributions.taxable_brokerage,
    "protection.review": protection.review,
    "tax.marginal_rate": tax.marginal_rate,
}


def get_calculator(name: str):
    fn = CALCULATORS.get(name)
    if fn is None:
        raise KeyError(f"unknown calculator {name!r}")
    return fn


__all__ = ["CalcContext", "CALCULATORS", "get_calculator"]
