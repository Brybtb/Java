"""Deterministic merge of extracted document fields into a client profile.

Boundary note (determinism contract): converting a scanned PDF (1040, estate
docs, P&C declarations) into structured fields is an OCR / AI step that is
NON-deterministic and therefore lives outside the engine — exactly like the
optional LLM explanation layer. Callers run that step (e.g. an OCR engine or an
LLM extractor) to produce a plain ``extracted`` dict, then pass it here. This
function is pure: same ``extracted`` -> same profile patch.
"""
from __future__ import annotations

import copy

from ..schemas.validate import validate_profile


def merge_1040(profile: dict, extracted: dict) -> dict:
    """Apply parsed 1040 fields to a profile (returns a new, validated profile)."""
    p = copy.deepcopy(profile)
    f = extracted.get("fields", {})

    p.setdefault("household", {})
    if f.get("filing_status"):
        p["household"]["filing_status"] = f["filing_status"]

    # Prefer wages for gross income; fall back to AGI.
    gross = f.get("wages") or f.get("agi")
    if gross is not None:
        p.setdefault("income", {})["gross_annual"] = gross

    # Record the document-derived tax facts for transparency.
    p.setdefault("_ingested", {})["form_1040"] = {
        k: f[k] for k in ("agi", "taxable_income", "total_tax") if k in f
    }
    return p


def merge_extracted(profile: dict, extracted: dict, *, validate: bool = True) -> dict:
    """Dispatch on the extraction source and merge. Validates the result unless
    the profile is still incomplete (intake in progress)."""
    src = extracted.get("source")
    if src == "form_1040":
        p = merge_1040(profile, extracted)
    else:
        raise ValueError(f"unsupported extraction source: {src!r}")
    if validate:
        try:
            validate_profile(p)
        except Exception:
            # Intake may be partial; leave validation to the caller/orchestrator.
            pass
    return p
