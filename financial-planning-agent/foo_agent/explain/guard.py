"""Guard for LLM-rendered explanations. Rejects any output that introduces a
rule id, source number, or dollar figure not present in the computed Result — so
the explanation layer can never smuggle a new decision past the engine."""
from __future__ import annotations

import json
import re

from ..engine.errors import FooError

_RULE_ID = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\b")
_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")


class GuardError(FooError):
    """The LLM explanation referenced something not in the Result."""


def _allowed_numbers(result: dict) -> set[str]:
    blob = json.dumps(result, default=str)
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", blob)}


def check(text: str, result: dict) -> list[str]:
    """Return a list of violations (empty == clean)."""
    issues: list[str] = []

    allowed_ids = {r["rule_id"] for r in result.get("recommendations", [])}
    allowed_ids |= {i["id"] for i in result.get("insights", [])}
    for m in _RULE_ID.findall(text):
        # Only police tokens that look like our namespaced ids (contain a dot and
        # an underscore segment), to avoid flagging ordinary prose like "e.g.".
        if m.startswith(("foo.", "contributions.", "emergency_fund.", "employer_match.",
                         "debt.", "tax.", "protection.")) and m not in allowed_ids:
            issues.append(f"unknown rule/calculator id referenced: {m}")

    allowed_nums = _allowed_numbers(result)
    for amt in _MONEY.findall(text):
        norm = amt.replace(",", "")
        if norm not in allowed_nums and norm.rstrip("0").rstrip(".") not in allowed_nums:
            issues.append(f"dollar figure not in Result: ${amt}")

    return issues


def validate(text: str, result: dict, *, strict: bool = True) -> str:
    issues = check(text, result)
    if issues and strict:
        raise GuardError("explanation rejected:\n  - " + "\n  - ".join(issues))
    return text
