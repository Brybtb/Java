"""Phase 2 optimizer correctness + determinism."""
from datetime import date

from foo_agent.optimize.roth_conversion import conversion_analysis
from foo_agent.optimize.social_security import claiming_analysis
from foo_agent.optimize.withdrawal_plan import withdrawal_plan
from foo_agent.rules.loader import load_params


def test_ss_actuarial_factors():
    a = claiming_analysis(3000, fra_age=67, longevity_age=90)
    by = {r["claim_age"]: r for r in a["by_claim_age"]}
    # 60 months early at FRA 67: 36*5/9% + 24*5/12% = 20% + 10% = 30% reduction.
    assert by[62]["factor"] == "0.7000"
    assert by[67]["factor"] == "1.0000"
    # 3 years delayed * 8% = 24% increase.
    assert by[70]["factor"] == "1.2400"
    assert by[62]["monthly"] == "2100.00"
    assert by[70]["monthly"] == "3720.00"


def test_ss_recommends_delaying_for_long_life():
    a = claiming_analysis(3000, fra_age=67, longevity_age=95)
    assert a["recommended_claim_age"] == 70
    assert a["breakeven_age_vs_62"] is not None


def test_ss_is_deterministic():
    assert claiming_analysis(2500, 67, 88) == claiming_analysis(2500, 67, 88)


def test_roth_bracket_fill():
    prof = {"schema_version": "1.0.0",
            "household": {"filing_status": "single", "state": "TX", "primary_age": 45},
            "income": {"gross_annual": 90000}, "expenses": {"monthly_essential": 3000}}
    params = load_params(date(2026, 6, 14), "TX")
    rc = conversion_analysis(prof, params, date(2026, 6, 14))
    # taxable = 90000 - 16100 std = 73900; 22% bracket top 105700 -> room 31800.
    assert rc["taxable_income"] == "73900.00"
    assert rc["current_marginal_rate"] == "0.22"
    first = rc["fill_targets"][0]
    assert first["conversion_room"] == "31800.00"
    assert first["blended_rate"] == "0.2200"


def test_withdrawal_order_taxable_first():
    prof = {"accounts": {"taxable": {"balance": 300000}, "employer_401k": {"balance": 500000},
                         "roth_ira": {"balance": 100000}}, "expenses": {"monthly_total": 7000}}
    wp = withdrawal_plan(prof)
    assert wp["order"] == ["taxable", "tax_deferred", "roth"]
    # 84000 need fully covered by taxable bucket.
    assert wp["first_year_draw"]["taxable"] == "84000.00"
    assert wp["shortfall"] == "0.00"
