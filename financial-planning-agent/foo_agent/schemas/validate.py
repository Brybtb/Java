"""Thin wrappers around jsonschema with friendly, path-prefixed errors.

Validation runs at three boundaries — ruleset load, profile entry, result exit —
so malformed data never reaches the engine and outputs are contract-guaranteed.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from jsonschema import Draft7Validator

from ..engine.errors import ProfileError, RuleError

_HERE = os.path.dirname(__file__)


@lru_cache(maxsize=None)
def _load_schema(name: str) -> dict:
    with open(os.path.join(_HERE, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _validate(instance: dict, schema_name: str, exc):
    validator = Draft7Validator(_load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        lines = []
        for e in errors[:10]:
            loc = "/".join(str(p) for p in e.path) or "(root)"
            lines.append(f"  - {loc}: {e.message}")
        raise exc(f"{schema_name} validation failed:\n" + "\n".join(lines))


def validate_rule(rule: dict) -> None:
    _validate(rule, "rule.schema.json", RuleError)


def validate_profile(profile: dict) -> None:
    _validate(profile, "profile.schema.json", ProfileError)


def validate_recommendation(result: dict) -> None:
    _validate(result, "recommendation.schema.json", RuleError)


def validate_scenario(scenario: dict) -> None:
    _validate(scenario, "scenario.schema.json", RuleError)


def validate_state(state: dict) -> None:
    _validate(state, "state.schema.json", RuleError)
