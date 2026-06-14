"""Dynamic workflow orchestrator: adaptive question flow + module selection,
all deterministic."""
import json
import os

from foo_agent.workflow.orchestrator import run

HERE = os.path.dirname(__file__)


def _load(name):
    with open(os.path.join(HERE, "golden", "profiles", name)) as f:
        return json.load(f)


def test_incomplete_profile_collects():
    r = run({})
    assert r["status"] == "collecting"
    assert r["next_question"]["field"] == "household.filing_status"


def test_young_saver_selects_core_only():
    r = run(_load("young_saver_TX.json"), trials=500)
    ids = {m["id"] for m in r["workflow"]["selected_modules"]}
    assert {"projection", "monte_carlo", "assetmap"} <= ids
    assert "social_security" not in ids
    assert "withdrawal_plan" not in ids
    assert r["optimizers"] == {}


def test_near_retiree_selects_optimizers():
    r = run(_load("near_retiree_TX.json"), trials=500)
    ids = {m["id"] for m in r["workflow"]["selected_modules"]}
    assert {"social_security", "withdrawal_plan", "roth_conversion"} <= ids
    assert r["optimizers"]["social_security"]["recommended_claim_age"] in range(62, 71)
    assert r["optimizers"]["withdrawal_plan"]["order"][0] == "taxable"


def test_workflow_is_deterministic():
    p = _load("near_retiree_TX.json")
    a = run(p, seed=7, trials=500)
    b = run(p, seed=7, trials=500)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
