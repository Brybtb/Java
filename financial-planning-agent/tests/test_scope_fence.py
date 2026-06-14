"""P0-GATE / P0-HARDEN: tasks.md parses; the scope fence flags out-of-scope and
out-of-package edits."""
from tools.scope_fence import classify, load_chunks


def test_tasks_md_parses():
    chunks = load_chunks()
    for cid in ["P0-CI", "P0-GATE", "C00", "C01", "C03", "C05"]:
        assert cid in chunks, f"{cid} missing from tasks.md"


def test_c03_scope_includes_copilot():
    chunks = load_chunks()
    files = chunks["C03"].get("files") or []
    assert any("copilot" in f for f in files)
    assert any("engine_tools" in f for f in files)


def test_every_chunk_has_status_and_files():
    for cid, c in load_chunks().items():
        assert c.get("status") in {"todo", "in_progress", "done", "blocked"}, cid
        assert c.get("files"), f"{cid} declares no files[] scope fence"


def test_classify_flags_out_of_package_and_out_of_scope():
    prefix = "financial-planning-agent/"
    allowed = {"tools/scope_fence.py"}
    changed = [
        "app.js",                                          # parent-repo file -> offender
        "financial-planning-agent/tools/scope_fence.py",   # in scope -> ok
        "financial-planning-agent/web/app.py",             # in package, out of scope -> offender
    ]
    offenders = classify(changed, allowed, prefix)
    assert "app.js" in offenders
    assert "financial-planning-agent/web/app.py" in offenders
    assert "financial-planning-agent/tools/scope_fence.py" not in offenders
