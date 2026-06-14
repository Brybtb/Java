"""Deterministic risk tolerance + portfolio risk alignment + stress tests
(Nitrogen / Riskalyze style).

Three deterministic pieces:
  1. A scored risk-tolerance questionnaire -> a 1-99 "Risk Number".
  2. A portfolio Risk Number derived from the equity allocation.
  3. Historical/hypothetical stress tests applied to the investable assets.

All pure: same answers + same allocation + same balances -> same numbers.
"""
from __future__ import annotations

from ..calculators.money import D, cents, whole
from ..projection.accounts import _investable_total

# Map stated tolerance -> target equity weight when no explicit allocation given.
TOLERANCE_EQUITY = {"conservative": D("0.40"), "moderate": D("0.60"), "aggressive": D("0.80")}

# Scored questionnaire. Each answer is an integer 1-5 (low->high risk appetite).
# Weights sum to 1; the weighted average (1-5) maps linearly onto a 1-99 scale.
QUESTIONNAIRE = [
    {"id": "time_horizon", "weight": D("0.25"),
     "prompt": "Years until you need this money? (1=<3, 5=>20)"},
    {"id": "loss_reaction", "weight": D("0.30"),
     "prompt": "A 20% drop in one year: 1=sell, 5=buy more"},
    {"id": "income_stability", "weight": D("0.15"),
     "prompt": "Income stability: 1=volatile, 5=very stable"},
    {"id": "experience", "weight": D("0.15"),
     "prompt": "Investing experience: 1=none, 5=extensive"},
    {"id": "goal_flexibility", "weight": D("0.15"),
     "prompt": "Flexibility on goal/timing: 1=none, 5=high"},
]

# Historical/hypothetical shocks: equity and bond total returns over the episode.
STRESS_SCENARIOS = [
    {"id": "gfc_2008", "name": "2008 Global Financial Crisis", "equity": D("-0.5097"), "bond": D("0.0524")},
    {"id": "covid_2020", "name": "2020 COVID crash (peak-trough)", "equity": D("-0.3379"), "bond": D("0.0300")},
    {"id": "stagflation_2022", "name": "2022 stocks & bonds selloff", "equity": D("-0.1811"), "bond": D("-0.1301")},
    {"id": "mild_correction", "name": "Hypothetical -10% equity correction", "equity": D("-0.1000"), "bond": D("0.0200")},
    {"id": "bear_market", "name": "Hypothetical -25% bear market", "equity": D("-0.2500"), "bond": D("0.0400")},
]


def risk_number_from_allocation(equity_pct) -> int:
    eq = D(equity_pct)
    if eq < 0:
        eq = D(0)
    if eq > 1:
        eq = D(1)
    # 0% equity -> 1, 100% equity -> 99 (linear, deterministic).
    return int((eq * 98 + 1).quantize(D("1")))


def questionnaire_risk_number(answers: dict) -> dict:
    total_w = D(0)
    acc = D(0)
    used = []
    for q in QUESTIONNAIRE:
        if q["id"] in answers:
            score = D(int(answers[q["id"]]))
            acc += score * q["weight"]
            total_w += q["weight"]
            used.append(q["id"])
    if total_w == 0:
        return {"risk_number": None, "answered": []}
    avg = acc / total_w  # 1..5
    rn = int(((avg - 1) / 4 * 98 + 1).quantize(D("1")))  # -> 1..99
    return {"risk_number": rn, "weighted_avg": str(avg.quantize(D("0.01"))), "answered": used}


def _equity_pct(profile: dict) -> D:
    alloc = (profile.get("risk", {}) or {}).get("allocation", {}) or {}
    if "equity_pct" in alloc:
        return D(alloc["equity_pct"])
    tol = (profile.get("risk", {}) or {}).get("tolerance", "moderate")
    return TOLERANCE_EQUITY.get(tol, D("0.60"))


def stress_test(investable, equity_pct) -> list[dict]:
    bal = D(investable)
    eq = D(equity_pct)
    bd = D(1) - eq
    rows = []
    for s in STRESS_SCENARIOS:
        ret = eq * s["equity"] + bd * s["bond"]
        loss = bal * ret
        rows.append({
            "id": s["id"], "name": s["name"],
            "portfolio_return": str(ret.quantize(D("0.0001"))),
            "projected_change": str(whole(loss)),
            "projected_value": str(whole(bal + loss)),
        })
    return rows


def risk_capacity_number(profile: dict, projection: dict | None) -> int:
    """Capacity = the ABILITY to take risk, from the plan (time horizon + funding),
    distinct from tolerance (willingness, from the questionnaire). 1-99."""
    age = int((profile.get("household", {}) or {}).get("primary_age", 0) or 0)
    retire_age = 65
    for g in profile.get("goals", []) or []:
        if g.get("type") == "retirement" and g.get("target_age"):
            retire_age = int(g["target_age"])
            break
    horizon = max(retire_age - age, 0)
    horizon_score = (D(min(horizon, 40)) / D(40)) * D(50)   # 0..50

    funded = D("0.5")
    if projection and projection.get("funded_ratio") is not None:
        funded = D(projection["funded_ratio"])
    funded_score = (min(funded, D(2)) / D(2)) * D(49)        # 0..49

    rn = int((horizon_score + funded_score + 1).quantize(D("1")))
    return max(1, min(99, rn))


def analyze(profile: dict, projection: dict | None = None) -> dict:
    equity_pct = _equity_pct(profile)
    portfolio_rn = risk_number_from_allocation(equity_pct)

    # Tolerance (willingness) — ONLY trustworthy from the questionnaire.
    answers = (profile.get("risk", {}) or {}).get("questionnaire", {}) or {}
    tol = questionnaire_risk_number(answers)
    tolerance_rn = tol.get("risk_number")
    if tolerance_rn is not None:
        tolerance_source = "questionnaire"
    else:
        # Weak fallback to the stated band, clearly labeled (not circular with
        # the portfolio: it reflects the stated tolerance, not the allocation).
        tolerance_rn = risk_number_from_allocation(
            TOLERANCE_EQUITY.get((profile.get("risk", {}) or {}).get("tolerance", "moderate"), D("0.60")))
        tolerance_source = "stated_band_fallback"

    capacity_rn = risk_capacity_number(profile, projection)
    # Recommended risk is the lesser of willingness and ability.
    recommended_rn = min(tolerance_rn, capacity_rn)

    gap = portfolio_rn - recommended_rn
    if abs(gap) <= 10:
        alignment = "aligned"
    elif gap > 10:
        alignment = "portfolio_too_aggressive"
    else:
        alignment = "portfolio_too_conservative"

    constraint = "capacity" if capacity_rn < tolerance_rn else "tolerance"

    investable = _investable_total(profile)
    return {
        "tolerance_risk_number": tolerance_rn,
        "tolerance_source": tolerance_source,
        "capacity_risk_number": capacity_rn,
        "recommended_risk_number": recommended_rn,
        "binding_constraint": constraint,
        "portfolio_risk_number": portfolio_rn,
        "equity_pct": str(equity_pct),
        "alignment": alignment,
        "investable_assets": str(whole(investable)),
        "stress_tests": stress_test(investable, equity_pct),
        "citation": "risk capacity (plan) vs tolerance (questionnaire) + historical episodes",
        "note": "Risk Number is 1-99. Capacity (ability, from horizon + funding) and "
                "tolerance (willingness, from the questionnaire) are distinct; the "
                "recommendation is the lesser. Provide a questionnaire for a true tolerance. "
                "Stress tests apply historical/hypothetical episode returns. Not predictive.",
    }
