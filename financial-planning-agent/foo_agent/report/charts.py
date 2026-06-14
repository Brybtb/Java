"""Deterministic charts as base64 PNG data URIs for embedding in the PDF/HTML.

Determinism: the Agg backend with a pinned style and DejaVu Sans (bundled with
matplotlib) renders byte-stable PNGs for a given matplotlib version and inputs.
No timestamps are written into the PNG.
"""
from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")  # headless, deterministic raster backend
import matplotlib.pyplot as plt  # noqa: E402


def _data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def projection_chart(projection: dict, primary: str = "#1f3a5f", accent: str = "#3d7ea6") -> str:
    path = projection.get("path", [])
    ages = [p["age"] for p in path]
    balances = [float(p["balance"]) for p in path]
    retire_age = projection.get("retire_age")

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.plot(ages, balances, color=primary, linewidth=2)
    ax.fill_between(ages, balances, color=accent, alpha=0.15)
    if retire_age:
        ax.axvline(retire_age, color=accent, linestyle="--", linewidth=1)
        ax.text(retire_age, max(balances or [0]) * 0.95, " retirement",
                color=accent, fontsize=8, va="top")
    ax.set_title("Projected portfolio balance (deterministic, mean return)", fontsize=10)
    ax.set_xlabel("Age", fontsize=8)
    ax.set_ylabel("Balance ($)", fontsize=8)
    ax.ticklabel_format(style="plain", axis="y")
    ax.grid(True, alpha=0.25)
    ax.tick_params(labelsize=7)
    return _data_uri(fig)


def assetmap_chart(profile: dict, primary: str = "#1f3a5f", accent: str = "#3d7ea6") -> str:
    """A one-page Asset-Map-style household balance sheet: members at the top,
    assets (left) vs. liabilities (right), and net worth. Deterministic layout."""
    from decimal import Decimal

    def D(x):
        try:
            return Decimal(str(x or 0))
        except Exception:
            return Decimal(0)

    accts = profile.get("accounts", {}) or {}
    assets = []
    for name in sorted(accts):
        a = accts[name]
        if isinstance(a, dict) and "balance" in a:
            assets.append((name.replace("_", " "), D(a["balance"])))
    debts = [(d.get("type", d.get("id", "debt")).replace("_", " "), D(d.get("balance", 0)))
             for d in (profile.get("debts", []) or [])]
    total_assets = sum((v for _, v in assets), Decimal(0))
    total_debt = sum((v for _, v in debts), Decimal(0))
    net_worth = total_assets - total_debt

    hh = profile.get("household", {}) or {}
    members = f"Ages {hh.get('primary_age', '?')}"
    if hh.get("spouse_age"):
        members += f" & {hh['spouse_age']}"
    title = f"{hh.get('filing_status','').replace('_',' ').title()} · {hh.get('state','')} · {members}"

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.add_patch(plt.Rectangle((0.5, 9), 9, 0.9, color=primary))
    ax.text(5, 9.45, f"Household Asset-Map — {title}", color="white", ha="center",
            va="center", fontsize=9, weight="bold")

    def column(x0, header, items, color):
        ax.text(x0 + 1.9, 8.5, header, ha="center", fontsize=9, weight="bold", color=color)
        y = 8.0
        for label, val in items[:9]:
            ax.add_patch(plt.Rectangle((x0, y - 0.42), 3.8, 0.5, color=color, alpha=0.12,
                                       ec=color))
            ax.text(x0 + 0.15, y - 0.17, label[:22], fontsize=7.5, va="center")
            ax.text(x0 + 3.65, y - 0.17, f"${val:,.0f}", fontsize=7.5, va="center", ha="right")
            y -= 0.6
        return y

    column(0.5, f"Assets  ${total_assets:,.0f}", assets, "#2e7d32")
    column(5.7, f"Liabilities  ${total_debt:,.0f}", debts or [("none", Decimal(0))], "#c62828")

    ax.add_patch(plt.Rectangle((0.5, 0.4), 9, 0.8, color=accent, alpha=0.18, ec=accent))
    ax.text(5, 0.8, f"Net worth:  ${net_worth:,.0f}", ha="center", va="center",
            fontsize=11, weight="bold", color=primary)
    return _data_uri(fig)


def montecarlo_chart(mc: dict, primary: str = "#1f3a5f", accent: str = "#3d7ea6") -> str:
    pct = mc.get("ending_balance_percentiles", {})
    labels = ["p10", "p25", "p50", "p75", "p90"]
    values = [pct.get(k, 0) for k in labels]

    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.bar(labels, values, color=[accent if k != "p50" else primary for k in labels])
    prob = mc.get("probability_of_success", 0)
    ax.set_title(f"Monte Carlo ending balance by percentile  —  P(success) = {prob:.0%}",
                 fontsize=10)
    ax.set_ylabel("Ending balance ($)", fontsize=8)
    ax.ticklabel_format(style="plain", axis="y")
    ax.grid(True, axis="y", alpha=0.25)
    ax.tick_params(labelsize=7)
    return _data_uri(fig)
