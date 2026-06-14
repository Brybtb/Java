"""Deterministic projection entry point."""
from __future__ import annotations

from datetime import date

from ..montecarlo.cma import CMA, load_cma
from .accounts import PlanInputs, build_plan_inputs
from .cashflow import project_deterministic
from .goals import retirement_readiness

__all__ = ["project", "build_inputs", "PlanInputs", "decumulation_projection"]


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


def decumulation_projection(profile: dict, as_of, data_dir: str | None = None) -> dict:
    """C08: the tax-aware bucket drawdown analysis (additive — separate from project()).

    Starts from the per-bucket balances at retirement (C07 accumulation), runs the
    deterministic tax-aware decumulation, and returns the schedule + lifetime tax +
    after-tax terminal wealth. Wired into the proposed/web surface by C09."""
    from ..rules.loader import load_params
    from .decumulation import decumulate

    pi, cma = build_inputs(profile, as_of, data_dir)
    det = project_deterministic(pi)
    bk = det["buckets"]
    buckets = {k: bk[k] for k in ("taxable", "tax_deferred", "tax_free")}

    as_of_d = _as_date(as_of)
    params = load_params(as_of_d, profile["household"]["state"], data_dir)
    tax = params["tax"]
    filing = profile["household"].get("filing_status", "single")
    age = int(profile.get("household", {}).get("primary_age", 0) or 0)
    birth_year = (as_of_d.year - age) if age else None

    return decumulate(
        buckets=buckets,
        retire_age=pi.retire_age,
        end_age=pi.end_age,
        annual_spend_retire=pi.annual_spend_retire,
        inflation=pi.inflation,
        mean_return=pi.mean_return,
        taxable_drag=pi.taxable_drag,
        ss_annual=pi.ss_annual,
        ss_claim_age=pi.ss_claim_age,
        birth_year=birth_year,
        brackets=tax["brackets"].get(filing, []),
        std_deduction=tax["standard_deduction"].get(filing, 0),
        terminal_ordinary_rate=cma.retirement_tax_rate,
    )
