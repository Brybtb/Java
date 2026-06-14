"""Derived facts. The condition DSL cannot iterate lists or recompute limits, so
we precompute a small set of boolean/numeric facts from the profile + params and
expose them under ``derived.*`` for rule conditions. These are pure functions of
the inputs, so they preserve determinism while keeping conditions readable.
"""
from __future__ import annotations

from .context import CalcContext
from . import contributions, debt, emergency_fund


def derive(ctx: CalcContext) -> dict:
    em_starter = emergency_fund.starter(ctx)
    em_full = emergency_fund.full(ctx)
    debt_hi = debt.high_interest(ctx)
    hsa = contributions.hsa_max(ctx)
    ira = contributions.ira_max(ctx)
    emp = contributions.employer_plan_max(ctx)

    hsa_eligible = bool(ctx.get("accounts.hsa.eligible", False))

    d = {
        "emergency_starter_funded": bool(em_starter["funded"]),
        "emergency_full_funded": bool(em_full["funded"]),
        "has_high_interest_debt": debt_hi["count"] > 0,
        "hsa_eligible": hsa_eligible,
        "hsa_maxed": bool(hsa["maxed"]),
        "ira_maxed": bool(ira["maxed"]),
        "employer_plan_maxed": bool(emp["maxed"]),
    }
    d["ready_for_taxable"] = (
        d["emergency_full_funded"]
        and not d["has_high_interest_debt"]
        and (d["hsa_maxed"] or not d["hsa_eligible"])
        and d["ira_maxed"]
        and d["employer_plan_maxed"]
    )
    d["roth_backdoor_candidate"] = ira["roth_route"] == "backdoor_or_traditional"
    return d
