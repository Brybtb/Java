"""Deterministic side-by-side comparison of a base profile against one or more
what-if scenarios — the engine behind MoneyGuidePro's "Play Zone" / eMoney's
"Decision Center", made reproducible."""
from __future__ import annotations

from .. import plan as _plan
from ..montecarlo import run as _mc
from ..projection import project as _project
from .scenario import apply_scenario


def _summary(profile: dict, as_of, seed: int, trials: int, data_dir) -> dict:
    proj = _project(profile, as_of, data_dir)
    mc = _mc(profile, as_of, seed=seed, trials=trials, data_dir=data_dir)
    rec = _plan(profile, as_of, data_dir=data_dir)
    return {
        "funded_ratio": proj["funded_ratio"],
        "retirement_status": proj["goal"]["status"],
        "balance_at_retirement": proj["balance_at_retirement"],
        "ending_balance": proj["ending_balance"],
        "probability_of_success": mc["probability_of_success"],
        "foo_steps": len(rec["recommendations"]),
    }


def compare(base: dict, scenarios: list[dict], as_of, *, seed: int = 424242,
            trials: int = 10000, data_dir: str | None = None) -> dict:
    """Return base + each scenario's headline metrics, computed deterministically."""
    rows = [{"id": "base", "label": "Base case", **_summary(base, as_of, seed, trials, data_dir)}]
    for sc in scenarios:
        modified = apply_scenario(base, sc)
        rows.append(
            {
                "id": sc["id"],
                "label": sc["label"],
                **_summary(modified, as_of, seed, trials, data_dir),
            }
        )
    return {"as_of": str(as_of), "seed": seed, "trials": trials, "scenarios": rows}
