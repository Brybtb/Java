"""C04: current-vs-proposed plan engine.

The engine maps its own FOO recommendations to a deterministic what-if scenario,
re-runs the engine, and attributes the funded_ratio / P(success) change to each
recommendation — moving the metrics only for recommendations whose action edits a
field the projection actually consumes, and flagging the rest as advisory (never a
fabricated delta)."""
import copy
import json
import os

import pytest

from foo_agent.projection.proposed import build
from foo_agent.scenarios.scenario import apply_scenario
from foo_agent.schemas.validate import validate_profile, validate_scenario
from foo_agent.workflow.orchestrator import run

HERE = os.path.dirname(__file__)
AS_OF = "2026-06-14"


def _load(name):
    with open(os.path.join(HERE, "golden", "profiles", name), "r", encoding="utf-8") as f:
        return json.load(f)


def _young():
    return _load("young_saver_TX.json")


# --- shape + baseline/proposed/delta ----------------------------------------
def test_build_returns_baseline_proposed_delta():
    out = build(_young(), AS_OF, trials=200)
    for k in ("baseline", "proposed", "delta", "steps"):
        assert k in out
    for m in (out["baseline"], out["proposed"]):
        assert "funded_ratio" in m and "probability_of_success" in m
    assert set(out["delta"]) == {"funded_ratio", "probability_of_success"}


def test_employer_match_is_modeled_and_lifts_funded_ratio():
    out = build(_young(), AS_OF, trials=200)
    match = next(s for s in out["steps"] if s["rule_id"] == "foo.employer_match.capture_full")
    assert match["modeled"] is True
    assert match["deltas"] == [{"path": "contributions.employer_401k.pct", "op": "set", "value": 0.06}]
    # capturing the full match raises the modeled deferral+match -> funded_ratio rises
    assert out["proposed"]["funded_ratio"] > out["baseline"]["funded_ratio"]
    assert out["delta"]["funded_ratio"] > 0


def test_advisory_recs_carry_zero_delta_and_a_reason():
    out = build(_young(), AS_OF, trials=200)
    for s in out["steps"]:
        if not s["modeled"]:
            assert s["delta_funded_ratio"] == 0.0
            assert s.get("reason")                 # honest reason, no fabricated movement
            assert "deltas" not in s               # no invented scenario edit


def test_debt_and_protection_are_advisory_not_modeled():
    out = build(_young(), AS_OF, trials=200)
    by_id = {s["rule_id"]: s for s in out["steps"]}
    assert by_id["foo.debt.high_interest"]["modeled"] is False
    assert by_id["foo.protect.dependents_priority"]["modeled"] is False


# --- coexisting Roth-IRA + pre-tax 401k, multiple modeled steps -------------
def _funded_no_debt_hsa():
    p = _young()
    p["accounts"]["cash_emergency"]["balance"] = 60000   # full reserve -> EF rules satisfied
    p["debts"] = []                                       # clear high-interest debt
    return p


def test_multiple_modeled_steps_compose():
    out = build(_funded_no_debt_hsa(), AS_OF, trials=200)
    modeled = [s for s in out["steps"] if s["modeled"]]
    ids = {s["rule_id"] for s in modeled}
    # match + HSA both fire and both edit DIFFERENT consumed fields (coexist)
    assert {"foo.employer_match.capture_full", "foo.hsa.max"} <= ids
    paths = {d["path"] for s in modeled for d in s["deltas"]}
    assert "contributions.employer_401k.pct" in paths
    assert "contributions.hsa.annual" in paths
    assert out["modeled_count"] == len(modeled) >= 2


def test_waterfall_steps_sum_to_total_delta():
    out = build(_funded_no_debt_hsa(), AS_OF, trials=200)
    summed = sum(s["delta_funded_ratio"] for s in out["steps"])
    assert summed == pytest.approx(out["delta"]["funded_ratio"], abs=1e-9)


# --- C9: taxable surplus is now MODELED (un-stranded from advisory) -----------
def _all_maxed():
    p = _young()
    p["accounts"]["cash_emergency"]["balance"] = 60000
    p["debts"] = []
    p["contributions"]["employer_401k"]["pct"] = 0.14
    p["contributions"]["hsa"]["annual"] = 8750
    p["contributions"]["roth_ira"]["annual"] = 7500
    return p


def test_taxable_surplus_is_now_modeled():
    out = build(_all_maxed(), AS_OF, trials=200)
    tax = next(s for s in out["steps"] if s["rule_id"] == "foo.taxable.hyper_accumulate")
    assert tax["modeled"] is True
    assert tax["deltas"][0]["path"] == "contributions.taxable.annual"
    assert out["modeled_count"] >= 1


# --- no-modeled-rec path (a household already in retirement) ------------------
def test_no_modeled_recs_means_zero_delta():
    p = _young()
    p["household"]["primary_age"] = 70           # in retirement -> only decum/protect (advisory) fire
    out = build(p, AS_OF, trials=200)
    assert out["modeled_count"] == 0
    assert out["delta"]["funded_ratio"] == 0.0
    assert out["proposed"]["funded_ratio"] == out["baseline"]["funded_ratio"]


# --- C9: tax-aware decumulation delta surfaced in the proposed output ---------
def test_proposed_carries_decumulation_delta():
    out = build(_all_maxed(), AS_OF, trials=200)
    dq = out["decumulation"]
    assert dq and "delta" in dq
    for side in ("baseline", "proposed"):
        assert "lifetime_tax_paid" in dq[side]
        assert "after_tax_terminal_wealth" in dq[side]
    assert int(dq["rmd_start_age"]) in (73, 75)
    assert dq["assumptions"]["citations"]          # provenance carried through (C10)


# --- correctness guards: valid scenario + valid proposed profile ------------
def test_proposed_scenario_and_profile_validate():
    out = build(_funded_no_debt_hsa(), AS_OF, trials=200)
    validate_scenario(out["proposed_scenario"])               # schema-valid what-if
    modified = apply_scenario(_funded_no_debt_hsa(), out["proposed_scenario"])
    validate_profile(modified)                                # engine-valid proposed profile


# --- determinism -------------------------------------------------------------
def test_proposed_is_deterministic():
    p = _young()
    a = build(copy.deepcopy(p), AS_OF, seed=7, trials=200)
    b = build(copy.deepcopy(p), AS_OF, seed=7, trials=200)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


# --- orchestrator wires it in (web reads result['proposed']) -----------------
def test_orchestrator_attaches_proposed_when_ready():
    r = run(_young(), AS_OF, trials=200)
    assert r["status"] == "ready"
    assert "proposed" in r
    # baseline reuses the orchestrator's own Result (engine funded_ratio is a Decimal string)
    assert r["proposed"]["baseline"]["funded_ratio"] == float(r["projection"]["funded_ratio"])


def test_orchestrator_propose_false_omits_it():
    r = run(_young(), AS_OF, trials=200, propose=False)
    assert "proposed" not in r


# --- C9: decumulation tool exposed on the engine-tool plane ------------------
def test_decumulation_tool_is_callable():
    from foo_agent.agents.engine_tools import call_tool, tool_catalog
    assert "decumulation" in {t["name"] for t in tool_catalog()}
    out = call_tool("decumulation", {"profile": _young(), "as_of": AS_OF})["output"]
    assert out["drawdown_order"] == ["taxable", "tax_deferred", "roth"]
    assert "lifetime_tax_paid" in out and out["assumptions"]["citations"]
