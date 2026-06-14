"""Guard for LLM-rendered text (explanations, copilot replies, proposer narration).

Rejects any output that introduces a rule/insight/module id, a dollar figure, a
percentage, or an age that is not present in the computed Result(s) for the turn —
so AI can phrase, but never author a number that reaches the client. Accepts a
single Result or a list of Results (a copilot turn may touch several tools).
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from ..engine.errors import FooError

_RULE_ID = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\b")
_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_AGE = re.compile(r"\bage\s+(\d{1,3})\b", re.I)
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Namespaced id prefixes we police (avoids flagging prose like "e.g."/"i.e.").
_ID_PREFIXES = (
    "foo.", "decum.", "contributions.", "emergency_fund.", "employer_match.",
    "debt.", "tax.", "protection.", "rmd.", "magi.", "decumulation.",
)


class GuardError(FooError):
    """The LLM text referenced something not in the Result(s)."""


def _as_list(result_or_results) -> list[dict]:
    if isinstance(result_or_results, list):
        return result_or_results
    return [result_or_results]


def _allowed_ids(results: list[dict]) -> set[str]:
    ids: set[str] = set()
    for r in results:
        for rec in r.get("recommendations", []) or []:
            ids.add(rec.get("rule_id", ""))
        for ins in r.get("insights", []) or []:
            ids.add(ins.get("id", ""))
        for m in (r.get("workflow", {}) or {}).get("selected_modules", []) or []:
            ids.add(m.get("id", ""))
    return ids


def _allowed_numbers(results: list[dict]) -> set[str]:
    """Every numeric token in the results, plus percent-form equivalents so that
    a rate stored as 0.22 also permits '22%'."""
    allowed: set[str] = set()
    for r in results:
        blob = json.dumps(r, default=str)
        for tok in _NUM.findall(blob):
            norm = tok.replace(",", "")
            allowed.add(norm)
            allowed.add(norm.rstrip("0").rstrip(".") if "." in norm else norm)
            try:
                d = Decimal(norm)
            except InvalidOperation:
                continue
            if 0 < d < 1:                       # 0.22 -> "22"
                allowed.add(str((d * 100).normalize()))
                allowed.add(str(int(d * 100)))
            if d == d.to_integral_value():       # 22 -> "22"
                allowed.add(str(int(d)))
    return allowed


def _num_in(value: str, allowed: set[str]) -> bool:
    norm = value.replace(",", "")
    if norm in allowed:
        return True
    trimmed = norm.rstrip("0").rstrip(".") if "." in norm else norm
    return trimmed in allowed


def check(text: str, result_or_results) -> list[str]:
    """Return a list of violations (empty == clean)."""
    results = _as_list(result_or_results)
    issues: list[str] = []

    allowed_ids = _allowed_ids(results)
    for m in _RULE_ID.findall(text):
        if m.startswith(_ID_PREFIXES) and m not in allowed_ids:
            issues.append(f"unknown rule/calculator id referenced: {m}")

    allowed_nums = _allowed_numbers(results)
    for amt in _MONEY.findall(text):
        if not _num_in(amt, allowed_nums):
            issues.append(f"dollar figure not in Result: ${amt}")
    for pct in _PERCENT.findall(text):
        if not _num_in(pct, allowed_nums):
            issues.append(f"percentage not in Result: {pct}%")
    for ag in _AGE.findall(text):
        if ag not in allowed_nums:
            issues.append(f"age not in Result: age {ag}")

    return issues


def validate(text: str, result_or_results, *, strict: bool = True) -> str:
    issues = check(text, result_or_results)
    if issues and strict:
        raise GuardError("text rejected (AI introduced data not in the Result):\n  - "
                         + "\n  - ".join(issues))
    return text
