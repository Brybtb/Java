"""Shared, read-only context handed to every calculator.

Calculators are pure functions of (profile facts, resolved params, as_of). They
never read the clock, the network, or globals. ``get`` resolves dotted paths so
calculators stay terse and tolerant of optional fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class CalcContext:
    profile: dict
    params: dict
    as_of: date

    def get(self, path: str, default: Any = None) -> Any:
        cur: Any = self.profile
        for seg in path.split("."):
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                return default
        return cur

    def param(self, path: str, default: Any = None) -> Any:
        cur: Any = self.params
        for seg in path.split("."):
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                return default
        return cur

    def age(self) -> int:
        return int(self.get("household.primary_age", 0) or 0)
