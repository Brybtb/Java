"""Audit trail. Every recommendation must be reconstructable from the trace:
which rules were evaluated, which fired and why, the input snapshot hash, and the
ruleset identity. This is the "why" behind every number."""
from __future__ import annotations

import hashlib
import json
from datetime import date


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def hash_input(profile: dict, as_of: date) -> str:
    payload = {"profile": profile, "as_of": as_of.isoformat()}
    return "sha256:" + hashlib.sha256(_canonical(payload).encode("ascii")).hexdigest()


class Trace:
    """Accumulates per-rule evaluation records in evaluation order."""

    def __init__(self) -> None:
        self.per_rule: list[dict] = []
        self.fired = 0
        self.evaluated = 0

    def record(self, rule_id: str, fired: bool, condition_result: bool, reason: str = "") -> None:
        self.evaluated += 1
        if fired:
            self.fired += 1
        entry = {"rule_id": rule_id, "fired": fired, "condition_result": condition_result}
        if reason:
            entry["reason"] = reason
        self.per_rule.append(entry)

    def to_dict(self, jurisdiction: str) -> dict:
        return {
            "rules_evaluated": self.evaluated,
            "rules_fired": self.fired,
            "jurisdiction_overlay": jurisdiction,
            "skipped": [e for e in self.per_rule if not e["fired"]],
            "per_rule": self.per_rule,
        }
