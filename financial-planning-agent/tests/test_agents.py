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


def test_guard_rejects_provenance_collision():
    # Digits that live ONLY inside provenance (hash, as_of, seed, trials) must NOT
    # become allowed figures (audit B7).
    result = {
        "input_hash": "sha256:409938abc",
        "as_of": "2026-06-14",
        "mc_seed": 424242,
        "trials": 2000,
        "projection": {"balance_at_retirement": 13140},
        "recommendations": [], "insights": [],
    }
    for bad in ("$409938", "$2,026", "$424242", "$2,000"):
        with pytest.raises(GuardError):
            validate(f"You'll have {bad}.", result)
    assert validate("You'll have $13,140 at retirement.", result)  # a genuine value passes


def test_guard_rejects_spelled_out():
    result = {"projection": {"balance_at_retirement": 13140}, "recommendations": [], "insights": []}
    with pytest.raises(GuardError):
        validate("You'll have about 1.4 million dollars.", result)
    with pytest.raises(GuardError):
        validate("That's two million dollars saved.", result)


# --- Copilot LLM mode (stub) + Gemini adapter --------------------------------
_COMPLETE_PROFILE = {
    "schema_version": "1.0.0", "as_of": AS_OF,
    "household": {"filing_status": "single", "state": "TX", "primary_age": 40},
    "income": {"gross_annual": 120000}, "expenses": {"monthly_essential": 4000},
    "accounts": {"cash_emergency": {"balance": 20000},
                 "employer_401k": {"balance": 100000, "match_offered": True,
                                   "match_rate": 0.5, "match_pct_cap": 0.06}},
    "contributions": {"employer_401k": {"pct": 0.03}}, "risk": {"tolerance": "moderate"},
}


def test_copilot_llm_mode_calls_tools_then_finals():
    calls = []

    def stub(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return json.dumps({"tool": "workflow_run", "args": {}})
        return json.dumps({"final": "Here is your plan. Capture your employer match first."})

    state = start(profile=dict(_COMPLETE_PROFILE), as_of=AS_OF)
    res = turn(state, "what's my plan?", llm=stub, as_of=AS_OF, seed=1, trials=300)
    assert res["status"] == "ready"
    assert [t["tool"] for t in res["tool_results"]] == ["workflow_run"]
    assert "employer match" in res["reply"]


def test_copilot_llm_guard_blocks_fabricated_number():
    def stub(prompt):
        return json.dumps({"final": "You'll definitely have $9,999,999 saved."})

    state = start(profile=dict(_COMPLETE_PROFILE), as_of=AS_OF)
    with pytest.raises(GuardError):
        turn(state, "how much?", llm=stub, as_of=AS_OF, seed=1, trials=300)


def test_gemini_adapter_requires_key(monkeypatch):
    from foo_agent.agents import llm as llm_mod
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        llm_mod.make_gemini()


def test_gemini_extract_text():
    from foo_agent.agents.llm import _extract_text
    ok = {"candidates": [{"content": {"parts": [{"text": '{"final":"hi"}'}]}}]}
    assert _extract_text(ok) == '{"final":"hi"}'
    blocked = {"promptFeedback": {"blockReason": "SAFETY"}}
    assert "SAFETY" in _extract_text(blocked)
