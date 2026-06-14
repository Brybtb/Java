"""Static determinism guard: no decision-path code reads the wall clock or uses
unseeded randomness. ``as_of`` is the only time input; randomness must come from a
seeded numpy Generator.

P0-CLOCK + P0-HARDEN: scans ALL of foo_agent/ line-by-line (new packages covered
automatically). Patterns anchor on the dangerous CALLEE so ALIASED imports cannot
bypass (`dt.now()`, `t.time()`, `import random as r`). A single line may opt out
with a `# noqa: P0-CLOCK` pragma (the I/O boundary, e.g. copilot's as_of default).
Hardened after the phase0-harness-review found the old literal-substring patterns
were trivially bypassable (aliases, secrets, os.urandom, uuid)."""
import os
import re

import foo_agent  # noqa: F401  (import-ability is part of the contract)

ROOT = os.path.dirname(os.path.dirname(__file__))
PKG = os.path.join(ROOT, "foo_agent")
PRAGMA = "noqa: P0-CLOCK"

# Clock reads, by callee name (alias-proof): x.now() / x.utcnow() / x.today() /
# gmtime() / localtime() / time.time / time_ns / monotonic / perf_counter / bare time().
CLOCK = [
    re.compile(r"\.now\s*\("),
    re.compile(r"\.utcnow\s*\("),
    re.compile(r"\.today\s*\("),
    re.compile(r"\.(?:gm|local)time\s*\("),
    re.compile(r"\btime\.time\b"),
    re.compile(r"\btime_ns\b"),
    re.compile(r"\bmonotonic\b"),
    re.compile(r"\bperf_counter\b"),
    re.compile(r"\btime\s*\("),  # bare time() from `from time import time`
]
# Unseeded randomness. The seeded numpy Generator idiom (default_rng / Generator /
# RandomState) is the ONLY allowed source, anywhere. Everything else is denied,
# including the stdlib random module (caught at its import so aliases can't hide).
RANDOMNESS = [
    re.compile(r"\bimport\s+random\b"),
    re.compile(r"\bfrom\s+random\s+import\b"),
    re.compile(r"(?<!np\.)\brandom\.\w"),
    re.compile(r"\bimport\s+secrets\b"),
    re.compile(r"\bsecrets\.\w"),
    re.compile(r"\bos\.urandom\b"),
    re.compile(r"\buuid\.uuid\d"),
    re.compile(r"\bSystemRandom\b"),
    re.compile(r"\bnp\.random\.(?!default_rng|Generator|RandomState)\w"),
]


def _py_files():
    for dirpath, _, names in os.walk(PKG):
        for n in names:
            if n.endswith(".py"):
                full = os.path.join(dirpath, n)
                yield full, os.path.relpath(full, ROOT).replace(os.sep, "/")


def _scan(patterns):
    offenders = []
    for full, rel in _py_files():
        with open(full, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if PRAGMA in line:
                    continue
                for pat in patterns:
                    if pat.search(line):
                        offenders.append(f"{rel}:{i}: /{pat.pattern}/")
    return offenders


def test_no_wall_clock_in_decision_path():
    offenders = _scan(CLOCK)
    assert not offenders, (
        "wall-clock read in the decision path (inject as_of; pragma only the I/O boundary):\n"
        + "\n".join(offenders)
    )


def test_no_unseeded_randomness():
    offenders = _scan(RANDOMNESS)
    assert not offenders, (
        "unseeded randomness (use a seeded numpy Generator):\n" + "\n".join(offenders)
    )


def test_clock_patterns_catch_aliased_forms():
    # Regression for the harness-review bypasses: aliases must NOT slip through.
    for s in ["dt.now()", "datetime.utcnow()", "x.today()", "t.time()",
              "time.time", "time.monotonic()", "time.perf_counter()", "time.time_ns()"]:
        assert any(p.search(s) for p in CLOCK), f"clock bypass not caught: {s!r}"


def test_randomness_patterns_catch_categories():
    for s in ["import random as r", "from random import randint", "random.random()",
              "import secrets", "secrets.token_hex()", "os.urandom(8)", "uuid.uuid4()",
              "SystemRandom()", "np.random.normal()"]:
        assert any(p.search(s) for p in RANDOMNESS), f"randomness bypass not caught: {s!r}"
    # The seeded Generator idiom is allowed everywhere.
    assert not any(p.search("rng = np.random.default_rng(seed)") for p in RANDOMNESS)


def test_plan_uses_as_of_not_clock(profile):
    a = foo_agent.plan(profile, "2026-06-14")
    b = foo_agent.plan(profile, "2026-01-01")
    assert a["as_of"] == "2026-06-14"
    assert b["as_of"] == "2026-01-01"
