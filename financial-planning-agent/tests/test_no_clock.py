"""Static guard: the decision path must never read the wall clock or use
unseeded randomness. ``as_of`` is the only time input."""
import os
import re

import foo_agent

ROOT = os.path.dirname(os.path.dirname(__file__))

# Decision-plane packages that must be clock- and randomness-free.
DECISION_PATHS = [
    "foo_agent/engine",
    "foo_agent/calculators",
    "foo_agent/rules/loader.py",
    "foo_agent/projection/cashflow.py",
    "foo_agent/projection/accounts.py",
]

FORBIDDEN = [
    re.compile(r"datetime\.now\b"),
    re.compile(r"\.today\("),
    re.compile(r"time\.time\b"),
    re.compile(r"\brandom\.\w"),       # stdlib random (numpy seeded RNG is allowed, MC only)
    re.compile(r"default_rng\b"),      # seeded RNG belongs only in montecarlo/
]


def _files():
    for p in DECISION_PATHS:
        full = os.path.join(ROOT, p)
        if os.path.isfile(full):
            yield full
        else:
            for dirpath, _, names in os.walk(full):
                for n in names:
                    if n.endswith(".py"):
                        yield os.path.join(dirpath, n)


def test_no_clock_or_random_in_decision_path():
    offenders = []
    for f in _files():
        with open(f, "r", encoding="utf-8") as fh:
            src = fh.read()
        for pat in FORBIDDEN:
            if pat.search(src):
                offenders.append(f"{os.path.relpath(f, ROOT)}: {pat.pattern}")
    assert not offenders, "clock/random in decision path:\n" + "\n".join(offenders)


def test_plan_uses_as_of_not_clock(profile):
    # Two different as_of dates must be allowed and reflected in output.
    a = foo_agent.plan(profile, "2026-06-14")
    b = foo_agent.plan(profile, "2026-01-01")
    assert a["as_of"] == "2026-06-14"
    assert b["as_of"] == "2026-01-01"
