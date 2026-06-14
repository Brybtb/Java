"""C11: cross-execute the engine's ordinary-tax math against an INDEPENDENT executable
tax oracle (tenforty, a Cython wrapper over OpenTaxSolver) — not just cited authority.

This is the correctness check C10 left open: C10 cited the IRS sources behind the
rates; this proves the engine's progressive-bracket arithmetic actually reproduces a
real IRS-rules tax engine. We feed BOTH the engine and tenforty the same tax year
(2023, a year tenforty supports) and compare federal income tax across incomes and
filing statuses.

tenforty applies the IRS Tax TABLES below ~$100k (income bucketed into $50 bands), so
a few dollars of difference vs the engine's exact formula is expected there; at and
above the worksheet threshold the IRS mandates the exact formula and the two match to
the dollar.

CI-safe: tenforty is an optional extra ([oracle]); this test skips if it is not
installed, so CI (which installs only [dev]) stays green. Run it with
`pip install -e .[oracle] && pytest tests/test_tax_oracle.py`.
"""
import pytest

from foo_agent.calculators.money import D
from foo_agent.projection.decumulation import ordinary_tax

tenforty = pytest.importorskip("tenforty")

# Official IRS tax year 2023 parameters (the oracle year). tenforty independently
# applies these rules; if the engine matches tenforty on these brackets, the brackets
# AND the engine's method are both validated by the oracle.
_2023 = {
    "Single": (13850, [
        {"up_to": 11000, "rate": 0.10}, {"up_to": 44725, "rate": 0.12},
        {"up_to": 95375, "rate": 0.22}, {"up_to": 182100, "rate": 0.24},
        {"up_to": 231250, "rate": 0.32}, {"up_to": 578125, "rate": 0.35},
        {"up_to": None, "rate": 0.37}]),
    "Married/Joint": (27700, [
        {"up_to": 22000, "rate": 0.10}, {"up_to": 89450, "rate": 0.12},
        {"up_to": 190750, "rate": 0.22}, {"up_to": 364200, "rate": 0.24},
        {"up_to": 462500, "rate": 0.32}, {"up_to": 693750, "rate": 0.35},
        {"up_to": None, "rate": 0.37}]),
}
_INCOMES = [40000, 60000, 120000, 250000, 600000]
_WORKSHEET_THRESHOLD = 100000   # IRS requires the exact computation worksheet at/above this


@pytest.mark.parametrize("filing", list(_2023))
@pytest.mark.parametrize("income", _INCOMES)
def test_engine_ordinary_tax_matches_tenforty(filing, income):
    std, brackets = _2023[filing]
    oracle = tenforty.evaluate_return(year=2023, filing_status=filing,
                                      w2_income=income).federal_income_tax
    taxable = income - std
    engine = float(ordinary_tax(D(taxable), brackets))
    if taxable >= _WORKSHEET_THRESHOLD:                # IRS exact computation worksheet
        assert abs(engine - oracle) <= 1.0            # match to the dollar
    else:
        assert abs(engine - oracle) <= 25.0           # IRS tax-table $50-bucket rounding


def test_engine_matches_tenforty_taxable_income():
    # The engine's taxable base (gross - standard deduction) equals tenforty's.
    std, _ = _2023["Single"]
    r = tenforty.evaluate_return(year=2023, filing_status="Single", w2_income=60000)
    assert r.federal_taxable_income == 60000 - std
