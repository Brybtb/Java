"""Load + validate the knowledge base, then freeze it.

Fail-closed is the rule: a malformed rule, an out-of-band order, a citation that
points at no known source, a schema-version mismatch, or params that do not
bracket the ``as_of`` date all raise rather than silently degrading.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

from ..engine.errors import AssumptionError, RuleError
from ..engine.ordering import sort_key, validate_order
from ..schemas.validate import validate_rule, validate_state
from ..version import RULESET_SCHEMA_VERSION

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


@dataclass(frozen=True)
class Ruleset:
    version: str
    schema_version: str
    checksum: str
    rules: tuple  # tuple of dict (sorted, immutable container)
    sources: dict  # int citation number -> source record
    manifest: dict

    def source_for(self, n: int) -> dict:
        return self.sources.get(n, {})


def load_ruleset(data_dir: str | None = None) -> Ruleset:
    data_dir = data_dir or _DATA_DIR

    manifest_path = os.path.join(data_dir, "ruleset.manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    declared = manifest.get("schema_version")
    if declared != RULESET_SCHEMA_VERSION:
        raise RuleError(
            f"ruleset schema_version {declared!r} != engine {RULESET_SCHEMA_VERSION!r}"
        )

    # Sources registry (citation integrity target).
    sources: dict[int, dict] = {}
    src_path = os.path.join(data_dir, "citations", "sources.json")
    with open(src_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    for s in raw.get("sources", []):
        sources[int(s["n"])] = s

    # Load every *.rules.yaml, sorted by filename for determinism.
    rule_files = sorted(
        fn for fn in os.listdir(data_dir) if fn.endswith(".rules.yaml")
    )
    seen_ids: set[str] = set()
    rules: list[dict] = []
    for fn in rule_files:
        with open(os.path.join(data_dir, fn), "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for rule in doc.get("rules", []):
            validate_rule(rule)
            validate_order(rule["id"], int(rule["order"]))
            rid = rule["id"]
            if rid in seen_ids:
                raise RuleError(f"duplicate rule id {rid!r} (in {fn})")
            seen_ids.add(rid)
            for c in rule["citations"]:
                if int(c) not in sources:
                    raise RuleError(
                        f"{rid}: citation [{c}] has no entry in sources.json"
                    )
            rules.append(rule)

    if not rules:
        raise RuleError(f"no rules found under {data_dir}")

    rules.sort(key=sort_key)
    checksum = "sha256:" + hashlib.sha256(
        _canonical([_canonical(r) for r in rules]).encode("ascii")
    ).hexdigest()

    return Ruleset(
        version=manifest["version"],
        schema_version=declared,
        checksum=checksum,
        rules=tuple(rules),
        sources=sources,
        manifest=manifest,
    )


def _select_dated(records: list[dict], as_of: date, what: str) -> dict:
    """Pick the record whose [effective_date, expiry_date) brackets as_of."""
    chosen = None
    for rec in records:
        eff = _parse_date(rec["effective_date"])
        exp = rec.get("expiry_date")
        exp_d = _parse_date(exp) if exp else None
        if eff <= as_of and (exp_d is None or as_of < exp_d):
            if chosen is None or eff > _parse_date(chosen["effective_date"]):
                chosen = rec
    if chosen is None:
        raise AssumptionError(
            f"no {what} brackets as_of {as_of.isoformat()} (fail closed)"
        )
    return chosen


def load_params(as_of: date, state: str, data_dir: str | None = None) -> dict:
    """Resolve federal base params + the state overlay for ``as_of``."""
    data_dir = data_dir or _DATA_DIR
    jdir = os.path.join(data_dir, "jurisdiction")

    with open(os.path.join(jdir, "_us_federal.params.yaml"), "r", encoding="utf-8") as f:
        federal_doc = yaml.safe_load(f) or {}
    federal_versions = federal_doc.get("versions", [federal_doc])
    federal = _select_dated(federal_versions, as_of, "federal params")

    state_path = os.path.join(jdir, f"{state}.params.yaml")
    if not os.path.exists(state_path):
        raise AssumptionError(
            f"unknown state {state!r}: no {state}.params.yaml (fail closed)"
        )
    with open(state_path, "r", encoding="utf-8") as f:
        state_doc = yaml.safe_load(f) or {}
    state_versions = state_doc.get("versions", [state_doc])
    state_params = _select_dated(state_versions, as_of, f"{state} params")
    validate_state(state_params)

    merged = dict(federal)
    merged.pop("effective_date", None)
    merged.pop("expiry_date", None)
    merged["state"] = state_params
    return merged
