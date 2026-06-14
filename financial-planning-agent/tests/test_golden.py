"""Golden snapshots for the deterministic planes (FOO plan + projection). The
expected files are committed; any behavioural drift fails loudly. Monte Carlo is
covered by reproducibility tests instead (to stay robust across numpy versions)."""
import json
import os

import foo_agent
from foo_agent.projection import project

HERE = os.path.dirname(__file__)
EXP = os.path.join(HERE, "golden", "expected")


def _load(name):
    with open(os.path.join(EXP, name), "r", encoding="utf-8") as f:
        return json.load(f)


def test_plan_matches_golden(profile):
    got = foo_agent.plan(profile)
    assert got == _load("young_saver_TX.plan.json")


def test_projection_matches_golden(profile):
    got = project(profile, profile["as_of"])
    assert got == _load("young_saver_TX.projection.json")
