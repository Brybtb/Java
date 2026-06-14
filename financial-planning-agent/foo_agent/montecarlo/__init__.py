"""Monte Carlo entry point (seeded, reproducible)."""
from __future__ import annotations

from ..version import DEFAULT_MC_SEED, DEFAULT_MC_TRIALS
from .cma import CMA, load_cma
from .simulator import simulate

__all__ = ["run", "load_cma", "CMA"]


def run(profile: dict, as_of, *, seed: int = DEFAULT_MC_SEED,
        trials: int = DEFAULT_MC_TRIALS, data_dir: str | None = None) -> dict:
    from ..projection import build_inputs  # lazy: avoids projection<->montecarlo cycle

    pi, cma = build_inputs(profile, as_of, data_dir)
    out = simulate(pi, seed=seed, trials=trials)
    out["cma_version"] = cma.version
    out["portfolio"] = cma.portfolio
    return out
