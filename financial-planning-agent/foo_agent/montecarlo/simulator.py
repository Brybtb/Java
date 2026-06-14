"""Seeded Monte Carlo retirement simulation.

Reproducibility is by construction: a fixed ``seed`` + the pinned CMA version +
the trial count fully determine the draw sequence (numpy PCG64 is
platform-independent), so identical inputs always yield identical probability of
success. This is how a *stochastic* method stays *deterministic* and auditable.
"""
from __future__ import annotations

import numpy as np

from ..projection.accounts import PlanInputs
from .results import summarize


def simulate(pi: PlanInputs, seed: int, trials: int) -> dict:
    years = pi.end_age - pi.start_age
    if years <= 0:
        raise ValueError("end_age must exceed start_age")

    rng = np.random.default_rng(seed)
    # (trials x years) nominal annual returns; clamp at -99% to avoid <-100%.
    draws = rng.normal(pi.mean_return, pi.stdev, size=(trials, years))
    np.clip(draws, -0.99, None, out=draws)

    # Pre-compute the contribution and spending schedules (nominal).
    infl = pi.inflation
    contrib_sched = np.zeros(years)
    spend_sched = np.zeros(years)
    for t in range(years):
        age = pi.start_age + t
        if age < pi.retire_age:
            contrib_sched[t] = pi.annual_contribution * ((1 + infl) ** t)
        else:
            yrs_in_ret = age - pi.retire_age
            spend_sched[t] = pi.annual_spend_retire * ((1 + infl) ** yrs_in_ret)

    bal = np.full(trials, float(pi.initial_balance))
    bal_at_retirement = None
    for t in range(years):
        bal = bal * (1 + draws[:, t])
        bal = bal + contrib_sched[t] - spend_sched[t]
        np.maximum(bal, 0.0, out=bal)
        if pi.start_age + t + 1 == pi.retire_age:
            bal_at_retirement = bal.copy()

    if bal_at_retirement is None:
        bal_at_retirement = bal.copy()

    return summarize(
        ending=bal,
        at_retirement=bal_at_retirement,
        seed=seed,
        trials=trials,
        pi=pi,
    )
