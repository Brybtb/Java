"""Scope fence: assert a chunk's git diff stays within its declared files[] (tasks.md).

A chunk may only touch the files it declares; this stops an automated build loop
from quietly editing out-of-scope code (audit FP-8). Reads the fenced ```yaml
blocks in tasks.md.

P0-HARDEN: the git toplevel is the PARENT foo-planner/ repo, not the package dir.
We diff toplevel-relative (NOT --relative, which silently hides every sibling file
outside the package) and reject anything not under the package prefix, so an edit
to a parent-repo file is a hard offender instead of invisible.

Usage:
    python tools/scope_fence.py <chunk_id> [base_ref]
Exits non-zero, listing any changed file outside the chunk's files[].
"""
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "tasks.md")
_BLOCK = re.compile(r"```yaml\n(.*?)```", re.S)


def load_chunks(path=TASKS):
    """Return {chunk_id: chunk_dict} parsed from the fenced yaml blocks in tasks.md."""
    text = open(path, "r", encoding="utf-8").read()
    chunks = {}
    for block in _BLOCK.findall(text):
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        for d in (data if isinstance(data, list) else [data]):
            if isinstance(d, dict) and d.get("id"):
                chunks[d["id"]] = d
    return chunks


def _git(*args):
    return subprocess.check_output(["git", "-C", ROOT, *args], text=True).strip()


def package_prefix():
    """The package's path relative to the git toplevel, e.g. 'financial-planning-agent/'."""
    return _git("rev-parse", "--show-prefix")


def changed_files(base):
    """Toplevel-relative changed paths (whole repo, NOT scoped by --relative)."""
    out = _git("diff", "--name-only", f"{base}...HEAD")
    return [f for f in out.splitlines() if f.strip()]


def classify(changed, allowed, prefix):
    """Pure: an offender is any changed path outside the package prefix, or inside
    it but not in the chunk's allowed (package-relative) files[]."""
    offenders = []
    for f in changed:
        if not f.startswith(prefix):
            offenders.append(f)            # out-of-package edit
        elif f[len(prefix):] not in allowed:
            offenders.append(f)            # in-package but out-of-scope
    return offenders


def check(chunk_id, base):
    chunks = load_chunks()
    if chunk_id not in chunks:
        raise SystemExit(f"unknown chunk {chunk_id!r}; known: {sorted(chunks)}")
    allowed = set(chunks[chunk_id].get("files") or [])
    return classify(changed_files(base), allowed, package_prefix()), allowed


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        raise SystemExit("usage: python tools/scope_fence.py <chunk_id> [base_ref]")
    cid = argv[0]
    base = argv[1] if len(argv) > 1 else "origin/claude/financial-planning-agent-b5yxqp"
    offenders, allowed = check(cid, base)
    if offenders:
        print(f"SCOPE FENCE FAIL ({cid}): changed files outside the allowed set:")
        for f in offenders:
            print("  " + f)
        print("allowed (package-relative):", sorted(allowed))
        return 1
    print(f"scope fence OK: {cid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
