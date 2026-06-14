"""P0-GATE: tasks.md must parse and declare each chunk's scope fence."""
from tools.scope_fence import load_chunks


def test_tasks_md_parses():
    chunks = load_chunks()
    # Phase 0 + the wedge chunks must all be present.
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
