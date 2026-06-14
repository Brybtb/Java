"""Apply a declarative what-if scenario (an ordered list of deltas) to a base
profile. Pure: returns a deep copy, never mutates the base — so the same base +
scenario always yields the same modified profile."""
from __future__ import annotations

import copy

from ..calculators.money import D
from ..engine.errors import ProfileError
from ..schemas.validate import validate_scenario


def _set_path(obj: dict, path: str, fn) -> None:
    parts = path.split(".")
    cur = obj
    for seg in parts[:-1]:
        if seg not in cur or not isinstance(cur[seg], dict):
            cur[seg] = {}
        cur = cur[seg]
    leaf = parts[-1]
    cur[leaf] = fn(cur.get(leaf))


def apply_scenario(base: dict, scenario: dict) -> dict:
    validate_scenario(scenario)
    profile = copy.deepcopy(base)
    for delta in scenario["deltas"]:
        path, op, value = delta["path"], delta["op"], delta["value"]
        if op == "set":
            _set_path(profile, path, lambda _old, v=value: v)
        elif op == "inc":
            _set_path(profile, path, lambda old, v=value: float(D(old or 0) + D(v)))
        elif op == "mul":
            _set_path(profile, path, lambda old, v=value: float(D(old or 0) * D(v)))
        else:  # pragma: no cover - schema prevents this
            raise ProfileError(f"unknown scenario op {op!r}")
    return profile
