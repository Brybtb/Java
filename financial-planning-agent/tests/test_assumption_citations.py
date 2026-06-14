"""C10: every tax/CMA assumption carries a real citation into sources.json.

Fail-closed: if a tax-engine constant or CMA assumption references a source number
that does not resolve, this test fails — so a confident figure can never reach
output uncited (CLAUDE.md: citations required, loader fails closed)."""
import os

import yaml

from foo_agent.calculators.money import D
from foo_agent.projection.decumulation import (
    ASSUMPTION_CITATIONS, LTCG_RATE, SS_TAXABLE_FRACTION, decumulate,
)
from foo_agent.rules.loader import load_ruleset

_CMA = os.path.join(os.path.dirname(__file__), "..", "foo_agent", "rules",
                    "data", "assumptions", "cma.2026.yaml")
_BR = [{"up_to": 12400, "rate": 0.10}, {"up_to": None, "rate": 0.22}]


def _sources():
    return load_ruleset().sources


def test_decumulation_assumption_citations_resolve():
    sources = _sources()
    cited = {n for ns in ASSUMPTION_CITATIONS.values() for n in ns}
    assert cited, "no citations declared"
    missing = [n for n in cited if not sources.get(n)]
    assert not missing, f"uncited assumption sources: {missing}"


def test_cma_tax_assumptions_are_cited():
    sources = _sources()
    cma = yaml.safe_load(open(_CMA))
    for field in ("taxable_drag_citations", "retirement_tax_rate_citations"):
        cites = cma.get(field)
        assert cites, f"{field} missing"
        assert all(sources.get(n) for n in cites), f"{field} has an unresolved source"


def test_sourced_values_match_authority():
    # The values we sourced: SS statutory max 85% (IRC §86), LTCG broad-middle 15%.
    assert SS_TAXABLE_FRACTION == D("0.85")
    assert LTCG_RATE == D("0.15")


def test_decumulate_output_carries_citations():
    out = decumulate(buckets={"taxable": 0, "tax_deferred": 100000, "tax_free": 0},
                     retire_age=70, end_age=72, annual_spend_retire=20000, inflation=0.02,
                     mean_return=0.05, taxable_drag=0.0, ss_annual=0, ss_claim_age=0,
                     birth_year=1950, brackets=_BR, std_deduction=15000)
    cites = out["assumptions"]["citations"]
    assert {"ss_taxable_fraction", "ltcg_rate", "rmd"} <= set(cites)
    sources = _sources()
    assert all(sources.get(n) for ns in cites.values() for n in ns)
