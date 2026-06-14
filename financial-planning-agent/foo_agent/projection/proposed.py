"""Current-vs-proposed planning (C04) — "what does following the plan change?"

Translate the engine's own FOO recommendations into a deterministic what-if
scenario, re-run the engine, and attribute the change in funded_ratio and
P(success) to each recommendation as an ordered (FOO) waterfall.

The hard rule is honesty, not coverage: a recommendation moves the metrics ONLY
if its action edits a field the deterministic projection actually consumes
(``projection/accounts.py``: ``contributions.employer_401k.pct``,
``contributions.roth_ira.annual``, ``contributions.hsa.annual``, or an investable
account balance). Recommendations whose target the projection does not model — a
cash reserve, debt payoff, a taxable-brokerage surplus, protection/estate — are
reported as *advisory* with a zero modeled delta and a plain reason. We never
fabricate a number for an action the model can't see.

NOTE (asset-location / decumulation, deliberately not yet modeled): the projection
is single-bucket — it blends taxable, tax-deferred, and Roth balances into one pot
with one blended retirement tax rate. So coexisting Roth-IRA + pre-tax-401k
contributions are summed correctly during accumulation, but their differing tax
treatment (Roth tax-free, 401(k)/IRA taxed at withdrawal with RMDs, taxable with
annual drag) and tax-efficient drawdown are out of scope here. That multi-bucket,
tax-aware accumulation+decumulation model is its own chunk; this engine surfaces
the gap (advisory rows) rather than papering over it.
"""
from __future__ import annotations

from ..scenarios.scenario import apply_scenario
from ..version import DEFAULT_MC_SEED, DEFAULT_MC_TRIALS

# Recommendations the projection structurally cannot model, with the honest reason
# shown to the advisor (never a fabricated funded_ratio delta). As of C9 the taxable
# surplus IS modeled (it funds the taxable bucket), so it is no longer here.
_ADVISORY_REASON = {
    "foo.emergency_fund.starter":
        "Cash reserve is liquidity, not an invested asset — excluded from the projection's investable pot.",
    "foo.emergency_fund.full":
        "Cash reserve is liquidity, not an invested asset — excluded from the projection's investable pot.",
    "foo.debt.high_interest":
        "Debt payoff / freed cash flow is not modeled by the retirement projection.",
    "foo.protect.dependents_priority":
        "Protection & estate are risk mitigation, not a portfolio input — not modeled in the projection.",
    "foo.protect.review_coverage":
        "Protection & estate are risk mitigation, not a portfolio input — not modeled in the projection.",
}
_ADVISORY_DEFAULT = "Advisory: the projection model does not consume this recommendation's target field."


def _clamp_pct(value: float) -> float:
    return max(0.0, min(1.0, value))


def _delta_for(rec: dict, profile: dict) -> list[dict]:
    """The scenario delta(s) that realize ``rec``, edited onto a field the projection
    consumes. Returns [] (advisory) when no such field realizes the recommendation —
    or when the recommendation's ``computed`` target is missing (never fabricate)."""
    rid = rec.get("rule_id")
    c = rec.get("computed") or {}
    try:
        if rid == "foo.employer_match.capture_full":
            return [{"path": "contributions.employer_401k.pct", "op": "set",
                     "value": _clamp_pct(float(c["target_pct"]))}]
        if rid == "foo.hsa.max":
            return [{"path": "contributions.hsa.annual", "op": "set", "value": float(c["annual_limit"])}]
        if rid == "foo.ira.max":
            return [{"path": "contributions.roth_ira.annual", "op": "set", "value": float(c["annual_limit"])}]
        if rid == "foo.employer_plan.max":
            gross = float((profile.get("income") or {}).get("gross_annual") or 0)
            if gross <= 0:
                return []
            return [{"path": "contributions.employer_401k.pct", "op": "set",
                     "value": _clamp_pct(float(c["annual_limit"]) / gross)}]
        if rid == "foo.taxable.hyper_accumulate":
            # C9: now modeled — the surplus funds the taxable bucket (grows net of drag).
            return [{"path": "contributions.taxable.annual", "op": "set",
                     "value": float(c["estimated_annual_surplus"])}]
    except (KeyError, TypeError, ValueError):
        return []   # missing/garbled computed target -> advisory, never invented
    return []


def _num(v):
    """The engine serializes money/ratios as Decimal strings; coerce to float for
    deterministic arithmetic (same input -> same float)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _metrics(res: dict) -> dict:
    proj = res.get("projection") or {}
    mc = res.get("monte_carlo") or {}
    goal = proj.get("goal") or {}
    return {
        "funded_ratio": _num(proj.get("funded_ratio")),
        "probability_of_success": _num(mc.get("probability_of_success")),
        "balance_at_retirement": _num(proj.get("balance_at_retirement")),
        "retirement_status": goal.get("status"),
    }


def _sub(a, b):
    if a is None or b is None:
        return None
    return a - b


def build(profile: dict, as_of=None, *, seed: int = DEFAULT_MC_SEED,
          trials: int = DEFAULT_MC_TRIALS, data_dir: str | None = None,
          baseline: dict | None = None) -> dict:
    """Baseline vs proposed metrics + a per-recommendation waterfall.

    Deterministic: same (profile, as_of, seed, trials, ruleset) -> identical output.
    ``baseline`` may be a previously-computed ``full_plan`` Result to avoid recomputing
    it (the orchestrator passes its own ready Result)."""
    from .. import full_plan   # lazy: keep projection import light

    base = baseline or full_plan(profile, as_of, seed=seed, trials=trials, data_dir=data_dir)
    base_m = _metrics(base)

    prev = base_m
    cumulative: list[dict] = []
    final = base
    steps: list[dict] = []
    for rec in base.get("recommendations") or []:
        deltas = _delta_for(rec, profile)
        common = {"rule_id": rec.get("rule_id"), "step": rec.get("step"),
                  "headline": rec.get("headline")}
        if deltas:
            cumulative = cumulative + deltas   # cumulative FOO-order waterfall
            modified = apply_scenario(profile, {"id": "proposed", "label": "Proposed plan",
                                                "deltas": cumulative})
            res = full_plan(modified, as_of, seed=seed, trials=trials, data_dir=data_dir)
            m = _metrics(res)
            steps.append({**common, "modeled": True, "deltas": deltas,
                          "funded_ratio": m["funded_ratio"],
                          "probability_of_success": m["probability_of_success"],
                          "delta_funded_ratio": _sub(m["funded_ratio"], prev["funded_ratio"]),
                          "delta_probability_of_success":
                              _sub(m["probability_of_success"], prev["probability_of_success"])})
            prev = m
            final = res
        else:
            steps.append({**common, "modeled": False,
                          "reason": _ADVISORY_REASON.get(rec.get("rule_id"), _ADVISORY_DEFAULT),
                          "delta_funded_ratio": 0.0, "delta_probability_of_success": 0.0})

    proposed_m = _metrics(final)
    return {
        "as_of": base.get("as_of"),
        "seed": seed,
        "trials": trials,
        "baseline": base_m,
        "proposed": proposed_m,
        "delta": {
            "funded_ratio": _sub(proposed_m["funded_ratio"], base_m["funded_ratio"]),
            "probability_of_success":
                _sub(proposed_m["probability_of_success"], base_m["probability_of_success"]),
        },
        "modeled_count": sum(1 for s in steps if s.get("modeled")),
        "steps": steps,
        "proposed_scenario": {"id": "proposed", "label": "Proposed plan", "deltas": cumulative},
        "decumulation": _decumulation_delta(profile, cumulative, base.get("as_of"), data_dir),
    }


def _decumulation_delta(profile, cumulative, as_of, data_dir):
    """C9: tax-aware decumulation for baseline vs proposed — lifetime tax + after-tax
    terminal wealth (deltas), the rmd start age, and the proposed drawdown/tax schedule.
    Additive enhancement; fails soft (returns None) so it never breaks the plan output."""
    from . import decumulation_projection
    try:
        base_d = decumulation_projection(profile, as_of, data_dir=data_dir)
        prop_profile = (apply_scenario(profile, {"id": "proposed", "label": "Proposed plan",
                                                 "deltas": cumulative}) if cumulative else profile)
        prop_d = decumulation_projection(prop_profile, as_of, data_dir=data_dir)
    except Exception:
        return None
    bt, pt = _num(base_d["lifetime_tax_paid"]), _num(prop_d["lifetime_tax_paid"])
    bw, pw = _num(base_d["after_tax_terminal_wealth"]), _num(prop_d["after_tax_terminal_wealth"])
    return {
        "rmd_start_age": base_d["rmd_start_age"],
        "drawdown_order": base_d["drawdown_order"],
        "baseline": {"lifetime_tax_paid": bt, "after_tax_terminal_wealth": bw},
        "proposed": {"lifetime_tax_paid": pt, "after_tax_terminal_wealth": pw},
        "delta": {"lifetime_tax_paid": _sub(pt, bt), "after_tax_terminal_wealth": _sub(pw, bw)},
        "schedule": prop_d["schedule"],
        "assumptions": prop_d["assumptions"],
    }
