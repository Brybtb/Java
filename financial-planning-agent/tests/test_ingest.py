"""Document ingestion: deterministic 1040 parse + merge."""
from foo_agent.ingest.extract import merge_extracted
from foo_agent.ingest.form1040 import parse_1040_text

SAMPLE = """Form 1040 (2026)
Filing Status: Married filing jointly
1a Total amount from Form(s) W-2, box 1 ......... 185,000
11 Adjusted gross income ......... 180,200
15 Taxable income ......... 148,000
24 Total tax ......... 24,310
"""


def test_parse_takes_amounts_not_line_numbers():
    f = parse_1040_text(SAMPLE)["fields"]
    assert f["wages"] == 185000.0
    assert f["agi"] == 180200.0
    assert f["taxable_income"] == 148000.0
    assert f["total_tax"] == 24310.0
    assert f["filing_status"] == "married_filing_jointly"


def test_parse_is_deterministic():
    assert parse_1040_text(SAMPLE) == parse_1040_text(SAMPLE)


def test_merge_into_profile():
    base = {"schema_version": "1.0.0",
            "household": {"state": "TX", "primary_age": 45},
            "expenses": {"monthly_essential": 4000}}
    merged = merge_extracted(base, parse_1040_text(SAMPLE), validate=False)
    assert merged["income"]["gross_annual"] == 185000.0
    assert merged["household"]["filing_status"] == "married_filing_jointly"
    assert merged["_ingested"]["form_1040"]["taxable_income"] == 148000.0
    # base profile is not mutated
    assert "income" not in base
