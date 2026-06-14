"""foo_agent — a deterministic, advisor-grade financial planning engine.

Public API
----------
    plan(profile, as_of=None)      -> Result dict (FOO recommendations + trace)

Determinism contract: for the same (profile, as_of, ruleset version, params), the
returned Result is byte-stable. ``as_of`` is the only time input; if omitted it is
read from the profile, never from the system clock.
"""
from __future__ import annotations

from datetime import date

from .calculators import CalcContext
from .calculators.derive import derive
from .compliance.wrapper import stamp
from .engine.errors import ProfileError
from .engine.evaluator import evaluate
from .engine.trace import hash_input
from .insights.observations import generate as generate_insights
from .rules.loader import Ruleset, load_params, load_ruleset
from .schemas.validate import validate_profile, validate_recommendation
from .version import DEFAULT_MC_SEED, DEFAULT_MC_TRIALS, __version__

__all__ = ["plan", "full_plan", "load_ruleset", "Ruleset", "__version__"]

SCHEMA_VERSION = "1.0.0"


def _resolve_as_of(profile: dict, as_of) -> date:
    if as_of is not None:
        return as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))
    raw = profile.get("as_of")
    if not raw:
        raise ProfileError("as_of not provided and profile has no 'as_of' field")
    return date.fromisoformat(str(raw))


def plan(profile: dict, as_of=None, *, ruleset: Ruleset | None = None,
         data_dir: str | None = None) -> dict:
    """Produce the deterministic Financial Order of Operations plan."""
    validate_profile(profile)
    as_of_d = _resolve_as_of(profile, as_of)

    rs = ruleset or load_ruleset(data_dir)
    state = profile["household"]["state"]
    params = load_params(as_of_d, state, data_dir)

    recommendations, trace = evaluate(profile, rs, params, as_of_d)

    # Sources actually cited by the fired recommendations, in ascending order.
    cited = sorted({c for rec in recommendations for c in rec["citations"]})
    sources = [rs.source_for(n) for n in cited if rs.source_for(n)]

    result = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": __version__,
        "ruleset_version": rs.version,
        "ruleset_checksum": rs.checksum,
        "cma_version": None,
        "mc_seed": None,
        "as_of": as_of_d.isoformat(),
        "input_hash": hash_input(profile, as_of_d),
        "recommendations": recommendations,
        "insights": [],
        "projection": None,
        "monte_carlo": None,
        "trace": trace.to_dict(state),
        "sources": sources,
    }
    stamp(result)
    validate_recommendation(result)
    return result


def full_plan(profile: dict, as_of=None, *, seed: int = DEFAULT_MC_SEED,
              trials: int = DEFAULT_MC_TRIALS, run_montecarlo: bool = True,
              data_dir: str | None = None) -> dict:
    """The complete advisor Result: FOO recommendations + deterministic
    projection + (optional) seeded Monte Carlo + citation-backed insights.

    Reproducible: same (profile, as_of, ruleset, CMA, seed, trials) -> same bytes.
    """
    # Lazy import: keeps numpy/projection out of the lightweight plan() path.
    from .montecarlo import run as run_montecarlo_fn
    from .projection import project as project_fn

    result = plan(profile, as_of, data_dir=data_dir)
    as_of_d = _resolve_as_of(profile, as_of)
    state = profile["household"]["state"]
    params = load_params(as_of_d, state, data_dir)

    proj = project_fn(profile, as_of_d, data_dir)
    result["projection"] = proj
    result["cma_version"] = proj["cma_version"]

    mc = None
    if run_montecarlo:
        mc = run_montecarlo_fn(profile, as_of_d, seed=seed, trials=trials, data_dir=data_dir)
        result["monte_carlo"] = mc
        result["mc_seed"] = seed

    facts = dict(profile)
    facts["params"] = params
    facts["derived"] = derive(CalcContext(profile=profile, params=params, as_of=as_of_d))
    facts["projection"] = proj
    facts["montecarlo"] = mc or {}
    result["insights"] = generate_insights(facts)

    validate_recommendation(result)
    return result
