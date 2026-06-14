"""Phase-4 correctness fixes (C1, C3, C4, C5, C7, C8)."""
from datetime import date

import foo_agent
from foo_agent.calculators import CalcContext
from foo_agent.calculators.magi import magi
from foo_agent.calculators.rmd import rmd_amount, rmd_start_age
from foo_agent.montecarlo import run as mc_run
from foo_agent.optimize.estate import analyze as estate
from foo_agent.optimize.risk import analyze as risk
from foo_agent.rules.loader import load_params

AS_OF = date(2026, 6, 14)


# C1 — MAGI is no longer raw gross
def test_magi_subtracts_pretax_deferral():
    prof = {"income": {"gross_annual": 200000},
            "contributions": {"employer_401k": {"pct": 0.10}, "hsa": {"annual": 4400}}}
    ctx = CalcContext(profile=prof, params={}, as_of=AS_OF)
    m = magi(ctx)
    # 200000 - 20000 deferral - 4400 hsa = 175600
    assert m["magi"] == "175600.00"


# C5 — RMDs
def test_rmd_age_and_amount():
    assert rmd_start_age(1955) == 73
    assert rmd_start_age(1962) == 75
    assert rmd_amount(72, 1_000_000, 1955) == 0          # before start age
    # age 75 divisor 24.6
    amt = rmd_amount(75, 1_000_000, 1955)
    assert abs(float(amt) - 1_000_000 / 24.6) < 1.0


# C3 — decumulation rules fire for a retiree
def test_decumulation_rules_fire_for_retiree():
    prof = {"schema_version": "1.0.0", "as_of": "2026-06-14",
            "household": {"filing_status": "single", "state": "TX", "primary_age": 75},
            "income": {"gross_annual": 40000}, "expenses": {"monthly_essential": 4000},
            "accounts": {"ira": {"balance": 800000}, "taxable": {"balance": 200000}},
            "goals": [{"type": "retirement", "target_age": 65}]}
    res = foo_agent.plan(prof)
    ids = {r["rule_id"] for r in res["recommendations"]}
    assert "decum.rmd.take_required_distribution" in ids
    assert "decum.drawdown.tax_efficient_order" in ids


# C4 — estate: prior gifts reduce exemption; NY state estate tax with cliff
def test_estate_prior_gifts_and_state_tax():
    prof = {"schema_version": "1.0.0",
            "household": {"filing_status": "single", "state": "NY", "primary_age": 80},
            "income": {"gross_annual": 100000}, "expenses": {"monthly_essential": 5000},
            "accounts": {"taxable": {"balance": 20000000}},
            "estate": {"prior_taxable_gifts": 5000000}}
    e = estate(prof, load_params(AS_OF, "NY"), AS_OF)
    # exemption 15M - 5M prior gifts = 10M; over = 20M - 10M = 10M * 40% = 4M
    assert e["applicable_exemption"] == "10000000"
    assert e["projected_federal_estate_tax"] == "4000000"
    # NY estate tax applies and is now dollar-modeled (> 0)
    assert e["state_estate_tax_applies"] is True
    assert float(e["projected_state_estate_tax"]) > 0


# C7 — risk capacity vs tolerance is not circular
def test_risk_capacity_vs_tolerance():
    prof = {"household": {"primary_age": 60}, "goals": [{"type": "retirement", "target_age": 62}],
            "accounts": {"taxable": {"balance": 100000}},
            "risk": {"tolerance": "aggressive", "allocation": {"equity_pct": 0.90},
                     "questionnaire": {"time_horizon": 1, "loss_reaction": 1,
                                       "income_stability": 1, "experience": 1, "goal_flexibility": 1}}}
    r = risk(prof, projection={"funded_ratio": "0.20"})
    assert r["tolerance_source"] == "questionnaire"
    assert r["tolerance_risk_number"] == 1            # all-low answers
    assert r["capacity_risk_number"] < 50             # short horizon, underfunded
    assert r["alignment"] == "portfolio_too_aggressive"


# C8 — Student-t Monte Carlo is reproducible and differs from normal
def test_montecarlo_student_t_reproducible_and_distinct():
    prof = {"schema_version": "1.0.0", "as_of": "2026-06-14",
            "household": {"filing_status": "single", "state": "TX", "primary_age": 40},
            "income": {"gross_annual": 100000}, "expenses": {"monthly_essential": 4000},
            "accounts": {"taxable": {"balance": 200000}},
            "goals": [{"type": "retirement", "target_age": 65}], "risk": {"tolerance": "moderate"}}
    a = mc_run(prof, "2026-06-14", seed=5, trials=3000, return_model="t")
    b = mc_run(prof, "2026-06-14", seed=5, trials=3000, return_model="t")
    assert a == b                                      # reproducible
    assert a["return_model"] == "t"
    norm = mc_run(prof, "2026-06-14", seed=5, trials=3000, return_model="normal")
    assert norm["probability_of_success"] != a["probability_of_success"] or \
        norm["ending_balance_percentiles"] != a["ending_balance_percentiles"]
