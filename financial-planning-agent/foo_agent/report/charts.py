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
