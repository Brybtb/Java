"""Schema, ordering, scenarios, insights, and explain-guard integration."""
import copy

import pytest

import foo_agent
from foo_agent.engine.errors import ProfileError, RuleError
from foo_agent.engine.ordering import band_label, validate_order
from foo_agent.explain.guard import GuardError, validate as guard_validate
from foo_agent.rules.loader import load_ruleset
from foo_agent.scenarios.compare import compare
from foo_agent.scenarios.scenario import apply_scenario


def test_all_rules_validate_and_have_citations():
    rs = load_ruleset()
    for rule in rs.rules:
        assert rule["citations"], f"{rule['id']} has no citations"
        validate_order(rule["id"], int(rule["order"]))
        band_label(int(rule["order"]))


def test_invalid_profile_rejected():
    with pytest.raises(ProfileError):
        foo_agent.plan({"schema_version": "1.0.0"})  # missing household/income/expenses


def test_unknown_state_fails_closed(profile):
    bad = copy.deepcopy(profile)
    bad["household"]["state"] = "ZZ"
    with pytest.raises(Exception):
        foo_agent.plan(bad)


def test_scenario_apply_is_pure(profile):
    sc = {"id": "raise_savings", "label": "Save more",
          "deltas": [{"path": "contributions.employer_401k.pct", "op": "set", "value": 0.15}]}
    before = copy.deepcopy(profile)
    modified = apply_scenario(profile, sc)
    assert profile == before  # base untouched
    assert modified["contributions"]["employer_401k"]["pct"] == 0.15


def test_scenario_compare_deterministic(profile):
    sc = {"id": "retire_later", "label": "Retire at 67",
          "deltas": [{"path": "goals", "op": "set", "value": [{"type": "retirement", "target_age": 67}]}]}
    a = compare(profile, [sc], profile["as_of"], trials=1000)
    b = compare(profile, [sc], profile["as_of"], trials=1000)
    assert a == b
    assert {r["id"] for r in a["scenarios"]} == {"base", "retire_later"}


def test_insights_fire_with_citations(profile):
    res = foo_agent.full_plan(profile, trials=1000)
    assert res["insights"]
    for ins in res["insights"]:
        assert ins["citations"]


def test_guard_rejects_unknown_id(profile):
    res = foo_agent.plan(profile)
    with pytest.raises(GuardError):
        guard_validate("You should follow foo.fake.rule now.", res)


def test_guard_allows_clean_text(profile):
    res = foo_agent.plan(profile)
    assert guard_validate("Capture your full employer match first.", res)
