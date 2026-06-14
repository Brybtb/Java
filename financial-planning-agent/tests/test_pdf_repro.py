"""White-labeled PDF must be byte-reproducible for the same Result + branding
(timestamps pinned to as_of via SOURCE_DATE_EPOCH)."""
import foo_agent
from foo_agent.report.branding import Branding
from foo_agent.report.pdf import render_html, render_pdf_bytes
from foo_agent.report.markdown import render_markdown


def test_html_is_deterministic(profile):
    res = foo_agent.full_plan(profile, trials=1000)
    a = render_html(res, Branding(firm_name="Acme"))
    b = render_html(res, Branding(firm_name="Acme"))
    assert a == b


def test_pdf_bytes_reproducible(profile):
    res = foo_agent.full_plan(profile, trials=1000)
    a = render_pdf_bytes(res, Branding(firm_name="Acme"))
    b = render_pdf_bytes(res, Branding(firm_name="Acme"))
    assert a == b
    assert a[:5] == b"%PDF-"


def test_branding_changes_output(profile):
    res = foo_agent.full_plan(profile, trials=1000)
    a = render_html(res, Branding(firm_name="Acme"))
    b = render_html(res, Branding(firm_name="Globex"))
    assert a != b
    assert "Globex" in b


def test_markdown_has_disclosures(profile):
    res = foo_agent.full_plan(profile, trials=1000)
    md = render_markdown(res)
    assert "Disclosures" in md
    assert "Decision-support draft" in md
