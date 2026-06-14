"""High-interest debt payoff. Avalanche ordering (highest APR first) minimizes
total interest; the threshold above which debt is "high interest" is a param so
it can move with prevailing safe rates."""
from __future__ import annotations

from .context import CalcContext
from .money import cents, D


def high_interest(ctx: CalcContext) -> dict:
    """Identify debts above the high-interest threshold and order them for
    avalanche payoff. Deterministic: sorted by (apr desc, balance desc, id)."""
    threshold = D(ctx.param("debt.high_interest_apr_threshold", "0.08"))
    debts = ctx.get("debts", []) or []

    flagged = []
    for d in debts:
        apr = D(d.get("apr", 0))
        if apr > threshold:
            bal = D(d.get("balance", 0))
            flagged.append(
                {
                    "id": d.get("id", ""),
                    "type": d.get("type", ""),
                    "balance": str(cents(bal)),
                    "apr": str(apr),
                    "annual_interest": str(cents(bal * apr)),
                    "_apr": apr,
                    "_bal": bal,
                }
            )

    # Total, stable order: APR desc, balance desc, id asc.
    flagged.sort(key=lambda x: (-x["_apr"], -x["_bal"], x["id"]))
    order = []
    total_balance = D(0)
    total_interest = D(0)
    for rank, f in enumerate(flagged, start=1):
        total_balance += f["_bal"]
        total_interest += f["_bal"] * f["_apr"]
        order.append(
            {
                "rank": rank,
                "id": f["id"],
                "type": f["type"],
                "balance": f["balance"],
                "apr": f["apr"],
                "annual_interest": f["annual_interest"],
            }
        )

    return {
        "threshold_apr": str(threshold),
        "count": len(order),
        "total_balance": str(cents(total_balance)),
        "total_annual_interest": str(cents(total_interest)),
        "payoff_order": order,
    }
