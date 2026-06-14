"""Goal-funding accounting on top of a deterministic projection. Phase 1 models
the retirement goal; additional goals (college, home) plug in here later."""
from __future__ import annotations

from ..calculators.money import D


def retirement_readiness(projection: dict) -> dict:
    funded_ratio = D(projection["funded_ratio"])
    if funded_ratio >= D("1.0"):
        status = "on_track"
    elif funded_ratio >= D("0.75"):
        status = "near_track"
    else:
        status = "behind"
    return {
        "goal": "retirement",
        "status": status,
        "funded_ratio": projection["funded_ratio"],
        "balance_at_retirement": projection["balance_at_retirement"],
        "target_nest_egg": projection["target_nest_egg"],
        "deterministic_success": projection["success"],
    }
