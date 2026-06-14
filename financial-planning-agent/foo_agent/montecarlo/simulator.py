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
    # C7: split accumulation contributions into the taxable bucket (which grows net
    # of the tax drag) and the untaxed buckets (tax-deferred + Roth). With a drag of
    # 0 (or no taxable money) this reproduces the pre-C7 single-pot path exactly.
    infl = pi.inflation
    tax_rate = pi.retirement_tax_rate
    drag = pi.taxable_drag
    taxable_c = np.zeros(years)
    untaxed_c = np.zeros(years)
    spend_sched = np.zeros(years)
    untaxed_contrib0 = pi.deferred_contrib + pi.free_contrib
    for t in range(years):
        age = pi.start_age + t
        if age < pi.retire_age:
            taxable_c[t] = pi.taxable_contrib * ((1 + infl) ** t)
            untaxed_c[t] = untaxed_contrib0 * ((1 + infl) ** t)
        else:
            spend = pi.annual_spend_retire * ((1 + infl) ** (age - pi.retire_age))
            ss = (pi.ss_annual * ((1 + infl) ** t)) if (pi.ss_claim_age and age >= pi.ss_claim_age) else 0.0
            net = max(spend - ss, 0.0)
            spend_sched[t] = net / (1 - tax_rate) if tax_rate < 1 else net

    taxed = np.full(trials, float(pi.taxable_balance))
    untaxed = np.full(trials, float(pi.deferred_balance + pi.free_balance))
    bal = taxed + untaxed
    bal_at_retirement = None
    for t in range(years):
        if pi.start_age + t < pi.retire_age:
            taxed = taxed * (1 + draws[:, t] - drag) + taxable_c[t]
            untaxed = untaxed * (1 + draws[:, t]) + untaxed_c[t]
            np.maximum(taxed, 0.0, out=taxed)
            np.maximum(untaxed, 0.0, out=untaxed)
            bal = taxed + untaxed
        else:
            # Collapsed (blended) decumulation — bucket-aware drawdown is C08.
            bal = bal * (1 + draws[:, t]) - spend_sched[t]
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
