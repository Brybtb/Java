"""Guyton-Klinger style spending guardrails. Provided as a pure, deterministic
helper for the Phase-2 dynamic-withdrawal model. Given a current withdrawal rate
relative to an initial rate, it signals whether to cut, raise, or hold spending.
"""
from __future__ import annotations

from ..calculators.money import D

# Defaults: if the current withdrawal rate drifts +20% above the initial rate,
# cut spending 10%; if it falls 20% below, raise spending 10%.
UPPER_GUARD = D("1.20")
LOWER_GUARD = D("0.80")
ADJUST = D("0.10")


def guardrail_action(initial_rate, current_rate) -> dict:
    init = D(initial_rate)
    cur = D(current_rate)
    if init <= 0:
        return {"action": "hold", "factor": "1.0"}
    ratio = cur / init
    if ratio > UPPER_GUARD:
        return {"action": "cut", "factor": str(D(1) - ADJUST)}
    if ratio < LOWER_GUARD:
        return {"action": "raise", "factor": str(D(1) + ADJUST)}
    return {"action": "hold", "factor": "1.0"}
