"""Load versioned Capital Market Assumptions and resolve the model portfolio for
a profile's stated risk tolerance. The CMA version is recorded in every Result so
a Monte Carlo run is reproducible."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import yaml

from ..engine.errors import AssumptionError

_ASSUMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules", "data", "assumptions")


@dataclass(frozen=True)
class CMA:
    version: str
    inflation: float
    mean_return: float
    stdev: float
    longevity_age: int
    longevity_age_joint: int
    default_retirement_age: int
    spending_replacement: float
    portfolio: str
    retirement_tax_rate: float


def load_cma(as_of: date, risk_tolerance: str = "moderate", data_dir: str | None = None) -> CMA:
    assump_dir = (
        os.path.join(data_dir, "assumptions") if data_dir else _ASSUMP_DIR
    )
    # Pick the CMA file whose effective_date brackets as_of (newest wins).
    chosen = None
    for fn in sorted(os.listdir(assump_dir)):
        if not fn.startswith("cma.") or not fn.endswith(".yaml"):
            continue
        with open(os.path.join(assump_dir, fn), "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        eff = date.fromisoformat(doc["effective_date"])
        exp = doc.get("expiry_date")
        exp_d = date.fromisoformat(exp) if exp else None
        if eff <= as_of and (exp_d is None or as_of < exp_d):
            if chosen is None or eff > date.fromisoformat(chosen["effective_date"]):
                chosen = doc
    if chosen is None:
        raise AssumptionError(f"no CMA brackets as_of {as_of.isoformat()} (fail closed)")

    portfolios = chosen.get("portfolios", {})
    port = portfolios.get(risk_tolerance) or portfolios.get("moderate")
    if port is None:
        raise AssumptionError(f"CMA has no portfolio for {risk_tolerance!r} or 'moderate'")

    return CMA(
        version=str(chosen["version"]),
        inflation=float(chosen["inflation"]),
        mean_return=float(port["mean_return"]),
        stdev=float(port["stdev"]),
        longevity_age=int(chosen.get("longevity_age", 95)),
        longevity_age_joint=int(chosen.get("longevity_age_joint", chosen.get("longevity_age", 95))),
        default_retirement_age=int(chosen.get("default_retirement_age", 65)),
        spending_replacement=float(chosen.get("spending_replacement", 0.8)),
        portfolio=risk_tolerance if risk_tolerance in portfolios else "moderate",
        retirement_tax_rate=float(chosen.get("retirement_tax_rate", 0.15)),
    )
