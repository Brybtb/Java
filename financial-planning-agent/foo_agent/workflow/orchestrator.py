"""Dynamic workflow orchestrator (helloplaybook-style, but deterministic).

Rather than always running everything, the orchestrator adapts to the client:

  1. If the profile is incomplete, it returns the next interview question and
     stops — driving guided data collection one step at a time.
  2. Once complete, it deterministically SELECTS which optional modules are
     relevant (Roth conversion, Social Security, withdrawal plan, Asset-Map)
     using safe-DSL conditions over the profile + derived facts, runs the core
     plan plus the selected modules, and returns them with the reason each was
     included.

Same inputs -> same workflow: which question is next, which modules fire, and
their outputs are all pure functions of the profile + as_of + ruleset/params.
"""
from __future__ import annotations

from datetime import date

from ..calculators import CalcContext
from ..calculators.derive import derive
from ..engine.condition import compile_condition
from ..interview.statemachine import next_question, remaining
from ..rules.loader import load_params

# Declarative module-selection rules. Conditions run over {profile, derived}.
MODULE_RULES = [
    {"id": "projection", "condition": "income.gross_annual > 0",
     "reason": "Always: multi-year retirement projection."},
    {"id": "monte_carlo", "condition": "income.gross_annual > 0",
     "reason": "Always: probability of success."},
    {"id": "assetmap", "condition": "income.gross_annual > 0",
     "reason": "Always: one-page household balance sheet."},
    {"id": "roth_conversion",
     "condition": "derived.roth_backdoor_candidate == true or household.primary_age >= 55",
     "reason": "Income near/above Roth phase-out, or approaching the conversion window."},
    {"id": "social_security",
     "condition": "exists(household.social_security.pia_monthly) or household.primary_age >= 50",
     "reason": "Within Social Security claiming-planning range, or PIA provided."},
    {"id": "withdrawal_plan",
     "condition": "household.primary_age >= 59",
     "reason": "At/near decumulation age; tax-efficient withdrawal sequencing applies."},
    {"id": "risk",
     "condition": "income.gross_annual > 0",
     "reason": "Always: risk-tolerance vs portfolio alignment and stress tests."},
    {"id": "estate",
     "condition": "exists(estate) or derived.high_net_worth == true or household.primary_age >= 60",
     "reason": "Estate assets present, high net worth, or near the wealth-transfer window."},
]


def _as_date(as_of) -> date:
    return as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))


def select_modules(profile: dict, params: dict, as_of: date) -> list[dict]:
    facts = dict(profile)
    facts["derived"] = derive(CalcContext(profile=profile, params=params, as_of=as_of))
    selected = []
    for m in MODULE_RULES:
        if compile_condition(m["condition"]).evaluate(facts):
            selected.append({"id": m["id"], "reason": m["reason"]})
    return selected


def run(profile: dict, as_of=None, *, seed: int | None = None, trials: int | None = None,
        data_dir: str | None = None, propose: bool = True) -> dict:
    # Phase 1: still collecting? Return the next question and stop.
    q = next_question(profile)
    if q is not None:
        return {
            "status": "collecting",
            "next_question": q,
            "remaining": remaining(profile),
            "message": "Answer the next question to continue the plan.",
        }

    # Phase 2: complete — select and run the applicable modules.
    from .. import full_plan
    from ..optimize.estate import analyze as estate_analyze
    from ..optimize.risk import analyze as risk_analyze
    from ..optimize.roth_conversion import conversion_analysis
    from ..optimize.social_security import claiming_analysis
    from ..optimize.withdrawal_plan import withdrawal_plan
    from ..version import DEFAULT_MC_SEED, DEFAULT_MC_TRIALS

    as_of_d = _as_date(as_of or profile.get("as_of"))
    state = profile["household"]["state"]
    params = load_params(as_of_d, state, data_dir)
    modules = select_modules(profile, params, as_of_d)
    module_ids = {m["id"] for m in modules}
    seed_v = seed if seed is not None else DEFAULT_MC_SEED
    trials_v = trials if trials is not None else DEFAULT_MC_TRIALS

    result = full_plan(
        profile, as_of_d,
        seed=seed_v,
        trials=trials_v,
        run_montecarlo="monte_carlo" in module_ids,
        data_dir=data_dir,
    )

    optimizers: dict = {}
    if "risk" in module_ids:
        optimizers["risk"] = risk_analyze(profile, result.get("projection"))
    if "estate" in module_ids:
        optimizers["estate"] = estate_analyze(profile, params, as_of_d)
    if "roth_conversion" in module_ids:
        optimizers["roth_conversion"] = conversion_analysis(profile, params, as_of_d)
    if "withdrawal_plan" in module_ids:
        optimizers["withdrawal_plan"] = withdrawal_plan(profile)
    if "social_security" in module_ids:
        ss = (profile.get("household", {}).get("social_security") or {})
        pia = ss.get("pia_monthly")
        if pia:
            fra = float(ss.get("fra_age", 67))
            longevity = int(ss.get("longevity_age", 90))
            optimizers["social_security"] = claiming_analysis(pia, fra, longevity)
        else:
            optimizers["social_security"] = {
                "status": "needs_input",
                "needed": "household.social_security.pia_monthly",
                "note": "Provide the estimated monthly benefit at full retirement age (from SSA).",
            }

    result["status"] = "ready"
    result["workflow"] = {"selected_modules": modules}
    result["optimizers"] = optimizers
    if propose:
        # Current-vs-proposed (C04): reuse the just-computed Result as the baseline so
        # we don't recompute it; the proposed engine re-runs only the modeled steps.
        from ..projection.proposed import build as build_proposed
        result["proposed"] = build_proposed(profile, as_of_d, seed=seed_v, trials=trials_v,
                                             data_dir=data_dir, baseline=result)
    return result
