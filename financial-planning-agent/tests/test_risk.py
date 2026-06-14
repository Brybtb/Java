"""Risk Number, alignment, and stress tests."""
from foo_agent.optimize.risk import (analyze, questionnaire_risk_number,
                                      risk_number_from_allocation, stress_test)


def test_risk_number_endpoints():
    assert risk_number_from_allocation(0) == 1
    assert risk_number_from_allocation(1) == 99
    assert 55 <= risk_number_from_allocation(0.6) <= 65


def test_questionnaire_scoring():
    answers = {"time_horizon": 5, "loss_reaction": 5, "income_stability": 5,
               "experience": 5, "goal_flexibility": 5}
    assert questionnaire_risk_number(answers)["risk_number"] == 99
    answers_low = {k: 1 for k in answers}
    assert questionnaire_risk_number(answers_low)["risk_number"] == 1


def test_stress_test_losses_negative_and_deterministic():
    a = stress_test(1000000, 0.8)
    b = stress_test(1000000, 0.8)
    assert a == b
    gfc = next(r for r in a if r["id"] == "gfc_2008")
    assert float(gfc["projected_change"]) < 0


def test_alignment_classification():
    prof = {"accounts": {"taxable": {"balance": 500000}},
            "risk": {"tolerance": "conservative", "allocation": {"equity_pct": 0.90}}}
    r = analyze(prof)
    assert r["alignment"] == "portfolio_too_aggressive"

    prof2 = {"accounts": {"taxable": {"balance": 500000}},
             "risk": {"tolerance": "moderate", "allocation": {"equity_pct": 0.60}}}
    assert analyze(prof2)["alignment"] == "aligned"
