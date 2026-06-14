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
    assert {"projection", "monte_carlo", "assetmap", "risk"} <= ids
    assert "social_security" not in ids
    assert "withdrawal_plan" not in ids
    # Only the always-on risk optimizer for a young saver — no SS/estate/roth.
    assert set(r["optimizers"].keys()) == {"risk"}


def test_near_retiree_selects_optimizers():
    r = run(_load("near_retiree_TX.json"), trials=500)
    ids = {m["id"] for m in r["workflow"]["selected_modules"]}
    # Age 63: SS/withdrawal/roth/risk/estate all engage; risk is always on.
    assert {"social_security", "withdrawal_plan", "roth_conversion", "risk", "estate"} <= ids
    assert r["optimizers"]["social_security"]["recommended_claim_age"] in range(62, 71)
    assert r["optimizers"]["withdrawal_plan"]["order"][0] == "taxable"
    assert r["optimizers"]["risk"]["alignment"] in (
        "aligned", "portfolio_too_aggressive", "portfolio_too_conservative")


def test_young_saver_excludes_estate():
    r = run(_load("young_saver_TX.json"), trials=500)
    ids = {m["id"] for m in r["workflow"]["selected_modules"]}
    assert "estate" not in ids        # age 34, net worth < threshold
    assert "risk" in ids              # risk is always on


def test_workflow_is_deterministic():
    p = _load("near_retiree_TX.json")
    a = run(p, seed=7, trials=500)
    b = run(p, seed=7, trials=500)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
