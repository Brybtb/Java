"""Tax-advantaged contribution headroom against versioned annual limits.

Limits, catch-ups, and phase-outs are all params resolved by ``as_of`` year, so
the math here never hard-codes a dollar figure that drifts.
"""
from __future__ import annotations

from .context import CalcContext
from .magi import magi as _magi
from .money import cents, D


def _headroom(limit, current) -> dict:
    limit, current = cents(limit), cents(current)
    gap = limit - current
    if gap < 0:
        gap = D(0)
    return {
        "annual_limit": str(limit),
        "current_annual": str(current),
        "headroom": str(cents(gap)),
        "maxed": current >= limit,
    }


def hsa_max(ctx: CalcContext) -> dict:
    coverage = ctx.get("accounts.hsa.coverage", "self")
    base = ctx.param(f"contribution_limits.hsa.{coverage}", 0)
    limit = D(base)
    if ctx.age() >= int(ctx.param("contribution_limits.hsa.catchup_age", 55)):
        limit += D(ctx.param("contribution_limits.hsa.catchup", 0))
    out = _headroom(limit, ctx.get("contributions.hsa.annual", 0))
    out["coverage"] = coverage
    return out


def ira_max(ctx: CalcContext) -> dict:
    """IRA headroom plus a deterministic Roth-vs-Traditional routing flag based
    on MAGI relative to the Roth phase-out for the filing status."""
    limit = D(ctx.param("contribution_limits.ira.limit", 0))
    if ctx.age() >= int(ctx.param("contribution_limits.ira.catchup_age", 50)):
        limit += D(ctx.param("contribution_limits.ira.catchup", 0))
    out = _headroom(limit, ctx.get("contributions.roth_ira.annual", 0))

    filing = ctx.get("household.filing_status", "single")
    magi = D(_magi(ctx)["_magi"])  # estimated MAGI (C1: no longer raw gross proxy)
    start = ctx.param(f"phaseouts.roth_ira.{filing}.start")
    end = ctx.param(f"phaseouts.roth_ira.{filing}.end")
    if start is None or end is None:
        route = "roth"
    elif magi < D(start):
        route = "roth"
    elif magi >= D(end):
        route = "backdoor_or_traditional"
    else:
        route = "roth_partial"
    out["roth_route"] = route
    out["magi"] = str(cents(magi))
    return out


def employer_plan_max(ctx: CalcContext) -> dict:
    """401(k)/403(b) elective-deferral headroom (the 402(g) limit)."""
    limit = D(ctx.param("contribution_limits.elective_deferral.limit", 0))
    if ctx.age() >= int(ctx.param("contribution_limits.elective_deferral.catchup_age", 50)):
        limit += D(ctx.param("contribution_limits.elective_deferral.catchup", 0))
    gross = D(ctx.get("income.gross_annual", 0))
    current = gross * D(ctx.get("contributions.employer_401k.pct", 0))
    return _headroom(limit, current)


def taxable_brokerage(ctx: CalcContext) -> dict:
    """Hyper-accumulation step: estimate annual surplus available to invest in a
    taxable account after essential expenses and current contributions."""
    gross = D(ctx.get("income.gross_annual", 0))
    essential_annual = D(ctx.get("expenses.monthly_essential", 0)) * 12
    cur_deferral = gross * D(ctx.get("contributions.employer_401k.pct", 0))
    other = (
        D(ctx.get("contributions.roth_ira.annual", 0))
        + D(ctx.get("contributions.hsa.annual", 0))
    )
    surplus = gross - essential_annual - cur_deferral - other
    if surplus < 0:
        surplus = D(0)
    return {"estimated_annual_surplus": str(cents(surplus))}
