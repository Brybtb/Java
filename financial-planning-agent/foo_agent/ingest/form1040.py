"""Deterministic Form 1040 text parser (Holistiplan-style intake).

The OCR / AI step that turns a PDF scan into text is inherently non-deterministic
and lives OUTSIDE the engine (see ingest/extract.py docstring). THIS parser is
pure: given the same extracted text it always returns the same structured fields.

Strategy: work line by line. A line is matched to a field by its label, then the
*largest* number on that line is taken as the value — this skips the small line
reference numbers (1a, 11, 15, 24) and captures the dollar amount.
"""
from __future__ import annotations

import re

_NUM = re.compile(r"\d[\d,]*(?:\.\d{2})?")

# field -> label matcher (case-insensitive, line-scoped)
_LABELS = [
    ("wages", re.compile(r"\bwages\b|salaries|line\s*1a|\b1a\b", re.I)),
    ("agi", re.compile(r"adjusted gross income|\bAGI\b|line\s*11\b|\b11\b", re.I)),
    ("taxable_income", re.compile(r"taxable income|line\s*15\b|\b15\b", re.I)),
    ("total_tax", re.compile(r"total tax|line\s*(?:22|24)\b|\b24\b", re.I)),
]

_FILING = [
    (re.compile(r"married filing jointly", re.I), "married_filing_jointly"),
    (re.compile(r"married filing separately", re.I), "married_filing_separately"),
    (re.compile(r"head of household", re.I), "head_of_household"),
    (re.compile(r"\bsingle\b", re.I), "single"),
]


def _largest_number(line: str):
    nums = [float(m.group(0).replace(",", "")) for m in _NUM.finditer(line)]
    return max(nums) if nums else None


def parse_1040_text(text: str) -> dict:
    fields: dict = {}
    filing = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if filing is None:
            for pat, val in _FILING:
                if pat.search(line):
                    filing = val
                    break
        for key, pat in _LABELS:
            if key in fields:
                continue
            if pat.search(line):
                val = _largest_number(line)
                if val is not None:
                    fields[key] = val
    if filing:
        fields["filing_status"] = filing
    return {"source": "form_1040", "fields": fields}
