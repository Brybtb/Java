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


def _draw_returns(rng, mean, stdev, size, model: str, t_df: int):
    """Annual return draws. 'normal' or 't' (Student-t, fat tails). Student-t is
    scaled to the target stdev so only the tail shape changes, not the variance.
    Deterministic given the seed for either model."""
    if model == "t":
        raw = rng.standard_t(t_df, size=size)          # var = df/(df-2)
        scale = stdev / np.sqrt(t_df / (t_df - 2.0))
        return mean + raw * scale
    return rng.normal(mean, stdev, size=size)


def simulate(pi: PlanInputs, seed: int, trials: int,
             return_model: str = "normal", t_df: int = 5) -> dict:
    years = pi.end_age - pi.start_age
    if years <= 0:
        raise ValueError("end_age must exceed start_age")

    rng = np.random.default_rng(seed)
    # (trials x years) nominal annual returns; clamp at -99% to avoid <-100%.
    draws = _draw_returns(rng, pi.mean_return, pi.stdev, (trials, years), return_model, t_df)
    np.clip(draws, -0.99, None, out=draws)

    # Pre-compute the contribution and spending schedules (nominal). Retirement
    # outflow nets Social Security and is grossed up for a blended tax rate (C6).
    infl = pi.inflation
    tax_rate = pi.retirement_tax_rate
    contrib_sched = np.zeros(years)
    spend_sched = np.zeros(years)
    for t in range(years):
        age = pi.start_age + t
        if age < pi.retire_age:
            contrib_sched[t] = pi.annual_contribution * ((1 + infl) ** t)
        else:
            spend = pi.annual_spend_retire * ((1 + infl) ** (age - pi.retire_age))
            ss = (pi.ss_annual * ((1 + infl) ** t)) if (pi.ss_claim_age and age >= pi.ss_claim_age) else 0.0
            net = max(spend - ss, 0.0)
            spend_sched[t] = net / (1 - tax_rate) if tax_rate < 1 else net

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
        return_model=return_model,
    )
