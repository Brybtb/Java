"""Static determinism guard: no decision-path code reads the wall clock or uses
unseeded randomness. ``as_of`` is the only time input; seeded RNG lives only in
montecarlo/.

P0-CLOCK: this scans ALL of foo_agent/ by default (denylist), with a small
explicit allowlist, so NEW packages are covered automatically and cannot quietly
reintroduce nondeterminism (audit FP-7)."""
import os
import re

import foo_agent  # noqa: F401  (import-ability is part of the contract)

ROOT = os.path.dirname(os.path.dirname(__file__))
PKG = os.path.join(ROOT, "foo_agent")

CLOCK = [
    re.compile(r"datetime\.now\b"),
    re.compile(r"\.today\("),
    re.compile(r"\btime\.time\b"),
]
RANDOMNESS = [
    re.compile(r"\brandom\.\w"),     # stdlib random anywhere in the decision plane
    re.compile(r"\bdefault_rng\b"),  # seeded numpy RNG belongs only in montecarlo/
]

# Seeded RNG is allowed here only.
RANDOM_ALLOWED_PREFIXES = ("foo_agent/montecarlo/",)
# I/O boundary that may legitimately touch the network/clock. The DECISION plane
# (engine, calculators, rules, projection, montecarlo, scenarios, insights,
# optimize, workflow, report, ingest) must stay clean; these turn/transport
# layers may default as_of from the clock.
#   - agents/llm.py     : live HTTP adapter.
#   - agents/copilot.py : chat turn layer; defaults as_of from the clock when the
#     caller omits it (audit D4 — to be tightened in C03 when the loop is reworked).
IO_ALLOWLIST = ("foo_agent/agents/llm.py", "foo_agent/agents/copilot.py")


def _py_files():
    for dirpath, _, names in os.walk(PKG):
        for n in names:
            if n.endswith(".py"):
                full = os.path.join(dirpath, n)
                yield full, os.path.relpath(full, ROOT).replace(os.sep, "/")


def _scan(patterns, skip_prefixes=()):
    offenders = []
    for full, rel in _py_files():
        if rel in IO_ALLOWLIST or rel.startswith(skip_prefixes):
            continue
        with open(full, "r", encoding="utf-8") as fh:
            src = fh.read()
        for pat in patterns:
            if pat.search(src):
                offenders.append(f"{rel}: /{pat.pattern}/")
    return offenders


def test_no_wall_clock_in_decision_path():
    offenders = _scan(CLOCK)
    assert not offenders, (
        "wall-clock read in the decision path (inject as_of instead):\n"
        + "\n".join(offenders)
    )


def test_no_unseeded_randomness_outside_montecarlo():
    offenders = _scan(RANDOMNESS, skip_prefixes=RANDOM_ALLOWED_PREFIXES)
    assert not offenders, (
        "randomness outside montecarlo/ (use a seeded RNG, MC only):\n"
        + "\n".join(offenders)
    )


def test_plan_uses_as_of_not_clock(profile):
    a = foo_agent.plan(profile, "2026-06-14")
    b = foo_agent.plan(profile, "2026-01-01")
    assert a["as_of"] == "2026-06-14"
    assert b["as_of"] == "2026-01-01"
