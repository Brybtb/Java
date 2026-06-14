"""The headline guarantee: identical inputs -> byte-identical output, regardless
of rule load order."""
import json
import random

import foo_agent
from foo_agent.engine.evaluator import evaluate
from foo_agent.rules.loader import Ruleset, load_params, load_ruleset
from datetime import date


def _canon(obj):
    return json.dumps(obj, sort_keys=True, default=str)


def test_plan_repeatable(profile):
    a = foo_agent.plan(profile)
    b = foo_agent.plan(profile)
    assert _canon(a) == _canon(b)


def test_plan_byte_stable_across_fresh_dicts(profile):
    import copy
    a = foo_agent.plan(copy.deepcopy(profile))
    b = foo_agent.plan(copy.deepcopy(profile))
    assert _canon(a) == _canon(b)


def test_rule_order_independence(profile):
    rs = load_ruleset()
    as_of = date.fromisoformat(profile["as_of"])
    params = load_params(as_of, profile["household"]["state"])

    base_recs, _ = evaluate(profile, rs, params, as_of)

    shuffled = list(rs.rules)
    random.Random(1).shuffle(shuffled)
    rs2 = Ruleset(rs.version, rs.schema_version, rs.checksum,
                  tuple(shuffled), rs.sources, rs.manifest)
    shuf_recs, _ = evaluate(profile, rs2, params, as_of)

    assert _canon(base_recs) == _canon(shuf_recs)


def test_checksum_stable():
    assert load_ruleset().checksum == load_ruleset().checksum


def test_result_embeds_versions(profile):
    r = foo_agent.plan(profile)
    assert r["engine_version"]
    assert r["ruleset_version"]
    assert r["ruleset_checksum"].startswith("sha256:")
    assert r["input_hash"].startswith("sha256:")
