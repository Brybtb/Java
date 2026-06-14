"""Deterministic projection entry point."""
from __future__ import annotations

from datetime import date

from ..montecarlo.cma import CMA, load_cma
from .accounts import PlanInputs, build_plan_inputs
from .cashflow import project_deterministic
from .goals import retirement_readiness

__all__ = ["project", "build_inputs", "PlanInputs"]


def _as_date(as_of) -> date:
    return as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))


def build_inputs(profile: dict, as_of, data_dir: str | None = None) -> tuple[PlanInputs, CMA]:
    risk = (profile.get("risk", {}) or {}).get("tolerance", "moderate")
    cma = load_cma(_as_date(as_of), risk, data_dir)
    return build_plan_inputs(profile, cma), cma


def project(profile: dict, as_of, data_dir: str | None = None) -> dict:
    pi, cma = build_inputs(profile, as_of, data_dir)
    det = project_deterministic(pi)
    det["cma_version"] = cma.version
    det["portfolio"] = cma.portfolio
    det["goal"] = retirement_readiness(det)
    return det
