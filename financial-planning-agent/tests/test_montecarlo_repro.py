"""Monte Carlo reproducibility: a stochastic method made deterministic by a
pinned seed + CMA + trial count."""
import json
import subprocess
import sys

from foo_agent.montecarlo import run
from foo_agent.projection import build_inputs
from foo_agent.montecarlo.simulator import simulate


def test_same_seed_same_probability(profile):
    a = run(profile, profile["as_of"], seed=42, trials=3000)
    b = run(profile, profile["as_of"], seed=42, trials=3000)
    assert a["probability_of_success"] == b["probability_of_success"]
    assert a["ending_balance_percentiles"] == b["ending_balance_percentiles"]


def test_different_seed_may_differ_but_records_seed(profile):
    a = run(profile, profile["as_of"], seed=1, trials=3000)
    b = run(profile, profile["as_of"], seed=2, trials=3000)
    assert a["seed"] == 1 and b["seed"] == 2


def test_seed_reproducible_across_processes(profile):
    code = (
        "import json,sys;from foo_agent.montecarlo import run;"
        "p=json.load(open('tests/golden/profiles/young_saver_TX.json'));"
        "print(run(p,p['as_of'],seed=7,trials=3000)['probability_of_success'])"
    )
    out1 = subprocess.check_output([sys.executable, "-c", code], cwd=".").strip()
    out2 = subprocess.check_output([sys.executable, "-c", code], cwd=".").strip()
    assert out1 == out2


def test_simulate_is_pure(profile):
    pi, _ = build_inputs(profile, profile["as_of"])
    a = simulate(pi, seed=99, trials=2000)
    b = simulate(pi, seed=99, trials=2000)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
