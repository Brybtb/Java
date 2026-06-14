"""Phase 4: Tool/Contract plane + Planning Copilot + generalized guard."""
import json

import pytest

from foo_agent.agents.copilot import start, turn
from foo_agent.agents.engine_tools import call_tool, tool_catalog
from foo_agent.explain.guard import GuardError, validate

AS_OF = "2026-06-14"

ANSWERS = {
    "filing_status": "single", "state": "TX", "primary_age": 35,
    "gross_income": 120000, "monthly_essential": 4000, "emergency_cash": 20000,
    "match_offered": True, "match_cap": 0.06, "current_deferral": 0.03,
    "hsa_eligible": False,
}


# --- Tool plane ---------------------------------------------------------------
def test_catalog_lists_core_tools():
    names = {t["name"] for t in tool_catalog()}
    assert {"workflow_run", "plan", "estate", "risk", "social_security"} <= names


def test_call_tool_stamps_and_is_deterministic():
    prof = {"schema_version": "1.0.0", "as_of": AS_OF,
            "household": {"filing_status": "single", "state": "TX", "primary_age": 40},
            "income": {"gross_annual": 100000}, "expenses": {"monthly_essential": 4000}}
    a = call_tool("plan", {"profile": prof, "as_of": AS_OF})
    b = call_tool("plan", {"profile": prof, "as_of": AS_OF})
    assert a["engine_version"] and a["output_hash"].startswith("sha256:")
    assert a["output_hash"] == b["output_hash"]
    assert "recommendations" in a["output"]


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        call_tool("does_not_exist", {})


# --- Copilot drives the dynamic workflow -------------------------------------
def _run_conversation(seed=1):
    state = start(profile={}, as_of=AS_OF)
    res = turn(state, None, as_of=AS_OF, seed=seed, trials=300)
    steps = 0
    while res["status"] == "collecting":
        qid = res["next_question"]["id"]
        assert qid in ANSWERS, f"unexpected question {qid}"
        res = turn(res["state"], ANSWERS[qid], as_of=AS_OF, seed=seed, trials=300)
        steps += 1
        assert steps < 20
    return res


def test_copilot_completes_and_returns_plan():
    res = _run_conversation()
    assert res["status"] == "ready"
    assert res["result"]["recommendations"]
    assert res["reply"]                       # guarded narration produced
    assert res["tool_results"][0]["tool"] == "workflow_run"


def test_copilot_is_deterministic():
    a = _run_conversation()
    b = _run_conversation()
    assert json.dumps(a["result"], sort_keys=True) == json.dumps(b["result"], sort_keys=True)


# --- Generalized guard --------------------------------------------------------
def test_guard_blocks_fabricated_money_and_percent_and_age():
    result = {"recommendations": [], "insights": [],
              "monte_carlo": {"probability_of_success": 0.82}, "as_of": AS_OF}
    with pytest.raises(GuardError):
        validate("You'll have $5,000,000 saved.", result)
    with pytest.raises(GuardError):
        validate("Your success rate is 99%.", result)   # 0.82 present, 99 is not
    with pytest.raises(GuardError):
        validate("Claim at age 71.", result)


def test_guard_allows_numbers_present_across_results():
    results = [{"monte_carlo": {"probability_of_success": 0.82}},
               {"optimizers": {}, "recommendations": [{"rule_id": "foo.ira.max"}]}]
    # 82% derived from 0.82; foo.ira.max present.
    assert validate("Success is 82%; next, foo.ira.max.", results)


def test_guard_clean_prose_passes():
    assert validate("Capture your full employer match first, then build reserves.",
                    {"recommendations": [], "insights": []})
