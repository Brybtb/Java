"""Modified Adjusted Gross Income (MAGI) estimate for Roth-eligibility routing.

Replaces the Phase-1 proxy that used gross income directly. MAGI here is gross
income less the common above-the-line items the engine knows about (pre-tax
employer-plan deferrals and HSA contributions). This is deterministic and a
materially better approximation; it intentionally does NOT claim to be a full
MAGI (which has Roth-specific add-backs), and that limitation is surfaced.
"""
from __future__ import annotations

from .context import CalcContext
from .money import cents, D


def magi(ctx: CalcContext) -> dict:
    gross = D(ctx.get("income.gross_annual", 0))

    # Pre-tax elective deferral (traditional unless explicitly Roth).
    deferral_pct = D(ctx.get("contributions.employer_401k.pct", 0))
    deferral_is_roth = bool(ctx.get("contributions.employer_401k.roth", False))
    pretax_deferral = D(0) if deferral_is_roth else gross * deferral_pct

    hsa = D(ctx.get("contributions.hsa.annual", 0))
    trad_ira = D(ctx.get("contributions.traditional_ira.annual", 0))

    est = gross - pretax_deferral - hsa - trad_ira
    if est < 0:
        est = D(0)
    return {
        "magi": str(cents(est)),
        "gross": str(cents(gross)),
        "above_the_line": str(cents(pretax_deferral + hsa + trad_ira)),
        "_magi": est,
        "note": "MAGI estimated as gross less known pre-tax deferrals + HSA + "
                "deductible traditional IRA; Roth-specific add-backs not modeled.",
    }
