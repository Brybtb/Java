"""Emergency-fund sizing. Targets are months of *essential* (not total)
expenses, a deliberately conservative CFP convention."""
from __future__ import annotations

from .context import CalcContext
from .money import cents, whole, D


def _result(current, target, monthly_suggested) -> dict:
    current, target = cents(current), cents(target)
    gap = target - current
    if gap < 0:
        gap = D(0)
    return {
        "current": str(current),
        "target": str(target),
        "gap": str(cents(gap)),
        "funded": current >= target,
        "monthly_suggested": str(cents(monthly_suggested)),
    }


def starter(ctx: CalcContext) -> dict:
    """Phase-1 starter buffer: a small fixed cushion before aggressive payoff."""
    essential = D(ctx.get("expenses.monthly_essential", 0))
    months = D(ctx.param("emergency_fund.starter_months", 1))
    floor = D(ctx.param("emergency_fund.starter_floor", 1000))
    target = max(essential * months, floor)
    current = D(ctx.get("accounts.cash_emergency.balance", 0))
    return _result(current, target, ctx.param("emergency_fund.starter_monthly", 250))


def full(ctx: CalcContext) -> dict:
    """Full reserve: 3-6 months of essential expenses, tuned by job stability."""
    essential = D(ctx.get("expenses.monthly_essential", 0))
    months = D(ctx.param("emergency_fund.full_months", 6))
    target = essential * months
    current = D(ctx.get("accounts.cash_emergency.balance", 0))
    suggested = ctx.param("emergency_fund.full_monthly", 500)
    out = _result(current, target, suggested)
    out["months_target"] = str(months)
    return out
