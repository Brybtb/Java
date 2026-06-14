"""Evaluate the declarative signals into a deterministic list of insights.

Like the rule engine, this is pure and citation-backed: every insight that fires
carries its source(s). Insights never *decide* anything — they annotate.
"""
from __future__ import annotations

import os
from functools import lru_cache

import yaml

from ..engine.condition import compile_condition

_SIGNALS_PATH = os.path.join(os.path.dirname(__file__), "signals.yaml")


@lru_cache(maxsize=1)
def _signals() -> list[dict]:
    with open(_SIGNALS_PATH, "r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("signals", [])


def generate(facts: dict) -> list[dict]:
    """Return the insights whose conditions hold, in declaration order."""
    out = []
    for sig in _signals():
        if compile_condition(sig["condition"]).evaluate(facts):
            out.append(
                {
                    "id": sig["id"],
                    "severity": sig["severity"],
                    "message": sig["message"],
                    "citations": list(sig.get("citations", [])),
                }
            )
    return out
