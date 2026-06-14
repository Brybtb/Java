"""Estate-tax projection + strategy modeling (TY2026 verified figures)."""
from datetime import date

from foo_agent.optimize.estate import analyze
from foo_agent.rules.loader import load_params

AS_OF = date(2026, 6, 14)


def _params(state="TX"):
    return load_params(AS_OF, state)


def test_single_under_exemption_no_tax():
    prof = {"schema_version": "1.0.0",
            "household": {"filing_status": "single", "state": "TX", "primary_age": 70},
            "income": {"gross_annual": 100000}, "expenses": {"monthly_essential": 4000},
            "accounts": {"taxable": {"balance": 5000000}}}
    e = analyze(prof, _params(), AS_OF)
    assert e["applicable_exemption"] == "15000000"
    assert e["projected_federal_estate_tax"] == "0"
    assert e["has_federal_estate_tax_exposure"] is False


def test_couple_over_exemption_taxed_at_40pct():
    prof = {"schema_version": "1.0.0",
            "household": {"filing_status": "married_filing_jointly", "state": "TX", "primary_age": 72},
            "income": {"gross_annual": 200000}, "expenses": {"monthly_essential": 8000},
            "accounts": {"taxable": {"balance": 40000000}}}
    e = analyze(prof, _params(), AS_OF)
    # 40,000,000 - 30,000,000 exemption = 10,000,000 * 40% = 4,000,000
    assert e["applicable_exemption"] == "30000000"
    assert e["projected_federal_estate_tax"] == "4000000"
    assert e["has_federal_estate_tax_exposure"] is True


def test_strategies_modeled_when_exposed():
    prof = {"schema_version": "1.0.0",
            "household": {"filing_status": "single", "state": "NY", "primary_age": 75},
            "income": {"gross_annual": 200000}, "expenses": {"monthly_essential": 8000},
            "accounts": {"taxable": {"balance": 30000000}},
            "estate": {"life_insurance_face": 4000000, "donees": 2, "planning_years": 10,
                       "slat_funding": 3000000}}
    e = analyze(prof, _params("NY"), AS_OF)
    sids = {s["id"] for s in e["strategies"]}
    assert {"annual_gifting", "ilit", "slat_grat"} <= sids
    assert e["state_estate_tax_applies"] is True  # NY is an estate-tax state
    for s in e["strategies"]:
        # tax saved is 40% of amount removed
        assert float(s["federal_tax_saved"]) == round(float(s["amount_removed_from_estate"]) * 0.40)


def test_deterministic():
    prof = {"schema_version": "1.0.0",
            "household": {"filing_status": "single", "state": "TX", "primary_age": 70},
            "income": {"gross_annual": 100000}, "expenses": {"monthly_essential": 4000},
            "accounts": {"taxable": {"balance": 20000000}}}
    assert analyze(prof, _params(), AS_OF) == analyze(prof, _params(), AS_OF)
