"""White-labeled PDF rendering via Jinja2 -> HTML -> WeasyPrint.

Reproducibility: WeasyPrint honors ``SOURCE_DATE_EPOCH`` for the PDF's embedded
timestamps, which we pin to the plan's ``as_of`` date. With deterministic charts
and a fixed template, the same Result + branding produces a byte-stable PDF.
"""
from __future__ import annotations

import base64
import os
import threading
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..compliance.wrapper import assert_compliant
from .branding import Branding
from .charts import assetmap_chart, montecarlo_chart, projection_chart

_TEMPLATES = os.path.join(os.path.dirname(__file__), "templates")


def _detail(rec: dict) -> str:
    c = rec.get("computed", {}) or {}
    if "forfeited_match_annual" in c:
        return (f"Raise to {c['target_pct']} of pay; "
                f"${c['forfeited_match_annual']}/yr match currently forfeited.")
    if "payoff_order" in c:
        return (f"{c['count']} debt(s), ${c['total_balance']} above "
                f"{c['threshold_apr']} APR; pay highest-APR first.")
    if "months_target" in c:
        return f"Target ${c['target']} ({c['months_target']} mo); gap ${c['gap']}."
    if "target" in c and "gap" in c:
        return f"Target ${c['target']}; gap ${c['gap']}."
    if "headroom" in c:
        return f"Headroom ${c['headroom']} of ${c['annual_limit']} limit."
    if "estimated_annual_surplus" in c:
        return f"Invest est. surplus ${c['estimated_annual_surplus']}/yr."
    if "suggested_life_coverage" in c:
        return (f"Suggested life cover ${c['suggested_life_coverage']}; "
                f"review: {', '.join(c.get('estate_checklist', []))}.")
    return ", ".join(f"{k}={v}" for k, v in c.items() if not isinstance(v, (list, dict)))


def _logo_uri(branding: Branding) -> str | None:
    if not branding.logo_path or not os.path.exists(branding.logo_path):
        return None
    ext = os.path.splitext(branding.logo_path)[1].lstrip(".").lower() or "png"
    with open(branding.logo_path, "rb") as f:
        return f"data:image/{ext};base64," + base64.b64encode(f.read()).decode("ascii")


def render_html(result: dict, branding: Branding, profile: dict | None = None) -> str:
    assert_compliant(result)
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["detail"] = _detail

    charts = {}
    proj = result.get("projection")
    if proj:
        charts["projection"] = projection_chart(proj, branding.primary_color, branding.accent_color)
    mc = result.get("monte_carlo")
    if mc:
        charts["montecarlo"] = montecarlo_chart(mc, branding.primary_color, branding.accent_color)
    if profile:
        charts["assetmap"] = assetmap_chart(profile, branding.primary_color, branding.accent_color)

    return env.get_template("report.html").render(
        result=result, branding=branding, charts=charts, logo_uri=_logo_uri(branding),
        optimizers=result.get("optimizers", {}),
    )


# B17: SOURCE_DATE_EPOCH is process-global; concurrent renders would clobber each
# other's value (a determinism leak under threading). Serialize the env-mutate +
# render so each PDF sees its own epoch. PDF export is rare, so the lock is cheap.
_PDF_EPOCH_LOCK = threading.Lock()


def render_pdf_bytes(result: dict, branding: Branding | None = None, profile: dict | None = None) -> bytes:
    from weasyprint import HTML  # local import: heavy, only needed for PDF

    branding = branding or Branding()
    # Pin embedded PDF timestamps to as_of (UTC midnight) for reproducibility.
    as_of = result.get("as_of")
    epoch = int(datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc).timestamp()) if as_of else 0
    with _PDF_EPOCH_LOCK:
        prev = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = str(epoch)
        try:
            html = render_html(result, branding, profile)
            return HTML(string=html).write_pdf()
        finally:
            if prev is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = prev


def write_pdf(result: dict, out_path: str, branding_path: str | None = None,
              profile: dict | None = None) -> str:
    branding = Branding.load(branding_path)
    pdf = render_pdf_bytes(result, branding, profile)
    with open(out_path, "wb") as f:
        f.write(pdf)
    return out_path
