"""Deterministic guided interview. Given a partial profile, returns the next
question to ask — the first whose target field is unanswered and whose
show-condition is met, in a fixed order. This delivers a helloplaybook-style
dynamic flow with zero nondeterminism."""
from __future__ import annotations

import os
from functools import lru_cache

import yaml

from ..engine.condition import MISSING, compile_condition

_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "questions.yaml")


@lru_cache(maxsize=1)
def _questions() -> list[dict]:
    with open(_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("questions", [])


def _resolve(profile: dict, field: str):
    cur = profile
    for seg in field.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return MISSING
    return cur


def next_question(profile: dict) -> dict | None:
    """Return the next question dict, or None when the interview is complete."""
    for q in _questions():
        if _resolve(profile, q["field"]) is not MISSING:
            continue
        cond = q.get("show_condition")
        if cond and not compile_condition(cond).evaluate(profile):
            continue
        return q
    return None


def remaining(profile: dict) -> int:
    """How many applicable questions are still unanswered."""
    count = 0
    for q in _questions():
        if _resolve(profile, q["field"]) is not MISSING:
            continue
        cond = q.get("show_condition")
        if cond and not compile_condition(cond).evaluate(profile):
            continue
        count += 1
    return count
