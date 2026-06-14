"""Loads the compliance policy and exposes the disclosure blocks + the
advisor-review gate that every Result must carry."""
from __future__ import annotations

import os
from functools import lru_cache

import yaml

_POLICY_PATH = os.path.join(os.path.dirname(__file__), "policy.yaml")


@lru_cache(maxsize=1)
def policy() -> dict:
    with open(_POLICY_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def disclosures() -> list[str]:
    # Collapse the folded-scalar whitespace into single spaces for clean output.
    return [" ".join(d.split()) for d in policy().get("disclosures", [])]


def requires_advisor_review() -> bool:
    return bool(policy().get("requires_advisor_review", True))
