"""Summarize Monte Carlo trial arrays into the reported, reproducible figures.
All floats are rounded to fixed precision so the JSON is byte-stable."""
from __future__ import annotations

import numpy as np


def _pct(arr: np.ndarray, q: float) -> int:
    return int(round(float(np.percentile(arr, q))))


def summarize(ending: np.ndarray, at_retirement: np.ndarray, seed: int, trials: int, pi) -> dict:
    success = float(np.mean(ending > 0.0))
    return {
        "probability_of_success": round(success, 4),
        "trials": int(trials),
        "seed": int(seed),
        "horizon_years": int(pi.end_age - pi.start_age),
        "retire_age": int(pi.retire_age),
        "end_age": int(pi.end_age),
        "assumptions": {
            "mean_return": pi.mean_return,
            "stdev": pi.stdev,
            "inflation": pi.inflation,
        },
        "ending_balance_percentiles": {
            "p10": _pct(ending, 10),
            "p25": _pct(ending, 25),
            "p50": _pct(ending, 50),
            "p75": _pct(ending, 75),
            "p90": _pct(ending, 90),
        },
        "balance_at_retirement_percentiles": {
            "p10": _pct(at_retirement, 10),
            "p50": _pct(at_retirement, 50),
            "p90": _pct(at_retirement, 90),
        },
    }
