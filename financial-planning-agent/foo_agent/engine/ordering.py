"""Canonical Financial Order of Operations bands.

Authors set each rule's integer ``order``; this module defines the meaning of the
bands and validates that every rule falls inside a known one. Encoding the
sequence here (rather than relying on file order) is what makes the priority
stable and auditable.
"""
from __future__ import annotations

from .errors import RuleError

# band lower bound -> (label, exclusive upper bound)
BANDS: list[tuple[int, str, int]] = [
    (100, "Essentials & starter emergency buffer", 200),
    (200, "Capture full employer match", 300),
    (300, "Pay off high-interest debt", 400),
    (400, "Full emergency reserve (3-6 months)", 500),
    (500, "Max HSA (if eligible)", 600),
    (600, "Max Roth/Traditional IRA", 700),
    (700, "Max employer retirement plan", 800),
    (800, "Hyper-accumulation (taxable / mega-backdoor / 529)", 900),
    (900, "Estate, insurance & advanced steps", 1000),
]


def band_label(order: int) -> str:
    for lo, label, hi in BANDS:
        if lo <= order < hi:
            return label
    raise RuleError(f"order {order} falls outside any known FOO band")


def validate_order(rule_id: str, order: int) -> None:
    band_label(order)  # raises if out of range
    if order < 0:
        raise RuleError(f"{rule_id}: order must be non-negative")


def sort_key(rule: dict):
    """Total, stable ordering key: (order, priority, id). Independent of the
    order rules were loaded from disk — the core determinism guarantee."""
    return (int(rule["order"]), int(rule.get("priority", 0)), str(rule["id"]))
