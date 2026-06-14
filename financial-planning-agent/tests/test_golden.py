"""Golden snapshots for the deterministic planes (FOO plan + projection). The
expected files are committed; any behavioural drift fails loudly with a
field-level diff (see tests/_golden_util.py). Monte Carlo is covered by
reproducibility tests instead (to stay robust across numpy versions)."""
import foo_agent
from foo_agent.projection import project

from tests._golden_util import assert_golden


def test_plan_matches_golden(profile):
    assert_golden(foo_agent.plan(profile), "young_saver_TX.plan.json")


def test_projection_matches_golden(profile):
    assert_golden(project(profile, profile["as_of"]), "young_saver_TX.projection.json")
