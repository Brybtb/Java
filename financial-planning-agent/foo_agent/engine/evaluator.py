"""The deterministic rule evaluator — the heart of the decision plane.

``evaluate`` is a pure function of (profile, ruleset, params, as_of). No network,
no clock (``as_of`` is injected), no randomness, no LLM. Rules are already in a
total order; we filter by date + jurisdiction, evaluate each condition against an
immutable fact view, and run the named calculator for those that fire.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

from ..calculators import CalcContext, get_calculator
from ..calculators.derive import derive
from ..rules.loader import Ruleset
from .condition import compile_condition
from .errors import RuleError
from .ordering import band_label, sort_key
from .trace import Trace


@lru_cache(maxsize=2048)
def _compiled(source: str):
    return compile_condition(source)


def _applies_jurisdiction(rule: dict, state: str) -> bool:
    j = rule["jurisdiction"]
    return j == "us_federal" or j == state


def _applies_date(rule: dict, as_of: date) -> bool:
    eff = date.fromisoformat(rule["effective_date"])
    if as_of < eff:
        return False
    exp = rule.get("expiry_date")
    if exp and as_of >= date.fromisoformat(exp):
        return False
    return True


def evaluate(profile: dict, ruleset: Ruleset, params: dict, as_of: date):
    """Return ``(recommendations, trace)``. Recommendations are ordered by FOO
    band; each carries its rule id, computed figures, citations, and rationale."""
    state = profile.get("household", {}).get("state", "")
    ctx = CalcContext(profile=profile, params=params, as_of=as_of)

    facts = dict(profile)
    facts["params"] = params
    facts["derived"] = derive(ctx)
    trace = Trace()
    recommendations = []
    step = 0

    # Defensive total ordering: even if a ruleset is passed unsorted, output is
    # identical. This is the core determinism guarantee.
    for rule in sorted(ruleset.rules, key=sort_key):
        rid = rule["id"]
        if not _applies_jurisdiction(rule, state):
            trace.record(rid, False, False, reason="jurisdiction mismatch")
            continue
        if not _applies_date(rule, as_of):
            trace.record(rid, False, False, reason="outside effective window")
            continue

        fired = _compiled(rule["condition"]).evaluate(facts)
        trace.record(rid, fired, fired)
        if not fired:
            continue

        calc_name = rule["action"]["calculator"]
        try:
            computed = get_calculator(calc_name)(ctx)
        except KeyError as exc:
            raise RuleError(f"{rid}: {exc}") from exc

        step += 1
        recommendations.append(
            {
                "step": step,
                "rule_id": rid,
                "band": band_label(int(rule["order"])),
                "headline": rule["title"],
                "computed": computed,
                "rationale_key": rule["rationale_key"],
                "citations": list(rule["citations"]),
                "confidence": rule.get("confidence", "medium"),
                "assumptions": list(rule.get("assumptions", [])),
            }
        )

    return recommendations, trace
