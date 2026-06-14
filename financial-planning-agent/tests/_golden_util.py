"""Structured golden-snapshot helpers (P0-GOLD).

Goldens still fail LOUDLY on any drift, but with a field-level diff so the cause
is obvious instead of an opaque "dicts differ". Regeneration is deliberate and
must record a WHY in tests/golden/GOLDEN_CHANGELOG.md, so an intentional fix is
never silently confused with a regression (audit FP-3).

Regenerate (only for an intentional, justified change):
    python -m tests._golden_util regen young_saver_TX.plan.json --why "C0X: <what changed + authority>"
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
EXP = os.path.join(HERE, "golden", "expected")
PROFILES = os.path.join(HERE, "golden", "profiles")
CHANGELOG = os.path.join(HERE, "golden", "GOLDEN_CHANGELOG.md")


def load_expected(name):
    with open(os.path.join(EXP, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def golden_diff(got, expected):
    """List of (path, expected_value, got_value) for every differing leaf."""
    fg, fe = _flatten(got), _flatten(expected)
    diffs = []
    for p in sorted(set(fg) | set(fe)):
        gv, ev = fg.get(p, "<missing>"), fe.get(p, "<missing>")
        if gv != ev:
            diffs.append((p, ev, gv))
    return diffs


def assert_golden(got, name, *, max_show=25):
    expected = load_expected(name)
    if got == expected:
        return
    diffs = golden_diff(got, expected)
    shown = [f"  {p}: expected {e!r} -> got {g!r}" for p, e, g in diffs[:max_show]]
    extra = "" if len(diffs) <= max_show else f"\n  ... +{len(diffs) - max_show} more"
    raise AssertionError(
        f"golden '{name}' drifted in {len(diffs)} field(s):\n"
        + "\n".join(shown) + extra
        + "\n\nIf INTENTIONAL, regenerate with a reason (logged to GOLDEN_CHANGELOG.md):\n"
        f'  python -m tests._golden_util regen {name} --why "<what changed and the authority>"'
    )


def _compute(name):
    """Recompute a golden from its profile by naming convention <base>.<kind>.json."""
    import foo_agent
    from foo_agent.projection import project

    base, kind = name.split(".")[0], name.split(".")[1]
    with open(os.path.join(PROFILES, base + ".json"), "r", encoding="utf-8") as f:
        prof = json.load(f)
    if kind == "plan":
        return foo_agent.plan(prof)
    if kind == "projection":
        return project(prof, prof["as_of"])
    raise SystemExit(f"don't know how to compute golden kind {kind!r} for {name!r}")


def regen(name, value, why):
    if not why or not why.strip():
        raise SystemExit("refusing to regenerate a golden without --why (audit FP-3)")
    with open(os.path.join(EXP, name), "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True, default=str)
        f.write("\n")
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        f.write(f"- {name}: {why.strip()}\n")
    print(f"regenerated {name}; logged WHY to {os.path.relpath(CHANGELOG, HERE)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 4 and a[0] == "regen" and a[2] == "--why":
        regen(a[1], _compute(a[1]), a[3])
    else:
        raise SystemExit('usage: python -m tests._golden_util regen <name> --why "reason"')
