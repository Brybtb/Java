"""Doc-drift guard (P0-DOC): documentation claims must match the code.

Catches the class of drift that bit us already — CLAUDE.md naming a Gemini model
string that the code no longer uses. We compare against the *literal default* in
llm.py source (not the env-resolved value), so a stray GEMINI_MODEL in the
environment cannot make this test lie.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _code_default_model() -> str:
    src = (ROOT / "foo_agent" / "agents" / "llm.py").read_text(encoding="utf-8")
    m = re.search(
        r"""os\.environ\.get\(\s*["']GEMINI_MODEL["']\s*,\s*["']([^"']+)["']""", src
    )
    assert m, "could not find the GEMINI_MODEL default literal in foo_agent/agents/llm.py"
    return m.group(1)


def test_claude_md_gemini_model_matches_code():
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    mentioned = set(re.findall(r"gemini-[0-9]+(?:\.[0-9]+)?-flash", claude_md))
    assert mentioned, "CLAUDE.md should reference the Gemini model so this guard has something to check"
    default = _code_default_model()
    assert mentioned == {default}, (
        f"CLAUDE.md references {sorted(mentioned)} but llm.py defaults to {default!r}. "
        "Update the doc (or the code) so they agree."
    )
