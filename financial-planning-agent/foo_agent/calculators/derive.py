"""Derived facts. The condition DSL cannot iterate lists or recompute limits, so
we precompute a small set of boolean/numeric facts from the profile + params and
expose them under ``derived.*`` for rule conditions. These are pure functions of
the inputs, so they preserve determinism while keeping conditions readable.
"""
from __future__ import annotations

from .context import CalcContext
from .money import D
from .rmd import rmd_amount, rmd_start_age
from . import contributions, debt, emergency_fund

_TAX_DEFERRED_KEYS = ("employer_401k", "ira", "traditional_ira", "403b")


def _retire_age(ctx: CalcContext) -> int:
    for g in ctx.get("goals", []) or []:
        if g.get("type") == "retirement" and g.get("target_age"):
            return int(g["target_age"])
    return 65


def _tax_deferred_balance(ctx: CalcContext) -> D:
    accts = ctx.get("accounts", {}) or {}
    bal = D(0)
    for k in _TAX_DEFERRED_KEYS:
        a = accts.get(k)
        if isinstance(a, dict):
            bal += D(a.get("balance", 0))
    return bal


def _estimated_net_worth(ctx: CalcContext) -> D:
    accts = ctx.get("accounts", {}) or {}
    nw = D(0)
    for a in accts.values():
        if isinstance(a, dict) and "balance" in a:
            nw += D(a["balance"])
    estate = ctx.get("estate", {}) or {}
    for k in ("real_estate", "business", "other_assets"):
        nw += D(estate.get(k, 0))
    for dbt in ctx.get("debts", []) or []:
        nw -= D(dbt.get("balance", 0))
    return nw


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

    net_worth = _estimated_net_worth(ctx)
    threshold = D(ctx.param("estate.review_threshold", 2000000))
    d["estimated_net_worth"] = str(net_worth)
    d["high_net_worth"] = net_worth >= threshold

    # Decumulation facts (C3).
    age = ctx.age()
    d["in_retirement"] = age >= _retire_age(ctx)
    birth_year = ctx.as_of.year - age if age else None
    td_balance = _tax_deferred_balance(ctx)
    d["has_tax_deferred"] = td_balance > 0
    d["rmd_active"] = age >= rmd_start_age(birth_year) and td_balance > 0
    return d
