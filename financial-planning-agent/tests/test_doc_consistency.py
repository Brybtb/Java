"""Doc-drift guard (P0-DOC + P0-HARDEN): documentation claims must match the code.

Catches the class of drift that bit us already — CLAUDE.md naming a Gemini model
the code no longer uses. We compare against the *literal default* in llm.py source
(not the env-resolved value — a stray GEMINI_MODEL in the environment must not make
this test lie). Hardened after the harness review found the old regex truncated
longer model names (gemini-2.5-flash-lite) and was brittle to the flash/pro family.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Whole Gemini model token, family-agnostic, no trailing punctuation.
_MODEL = r"gemini-[a-z0-9]+(?:[.\-][a-z0-9]+)*"


def _code_default_model() -> str:
    # Strip comment lines so a stale commented default cannot poison the source of truth.
    raw = (ROOT / "foo_agent" / "agents" / "llm.py").read_text(encoding="utf-8")
    src = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("#"))
    m = re.search(
        r"""(?:os\.environ\.get|os\.getenv)\(\s*["']GEMINI_MODEL["']\s*,\s*["'](""" + _MODEL + r""")["']""",
        src, re.I,
    )
    assert m, "could not find a gemini-* GEMINI_MODEL default literal in foo_agent/agents/llm.py"
    return m.group(1)


def test_claude_md_gemini_model_matches_code():
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    mentioned = set(re.findall(_MODEL, claude_md, re.I))
    assert mentioned, "CLAUDE.md should reference the Gemini model so this guard has something to check"
    default = _code_default_model()
    assert mentioned == {default}, (
        f"CLAUDE.md references {sorted(mentioned)} but llm.py defaults to {default!r}. "
        "Update the doc (or the code) so they agree."
    )


def test_model_regex_captures_full_token():
    # Regression: the old pattern stopped at '-flash' and let 'gemini-2.5-flash-lite'
    # masquerade as 'gemini-2.5-flash'. The full token must be captured.
    assert re.findall(_MODEL, "model `gemini-2.5-flash-lite`", re.I) == ["gemini-2.5-flash-lite"]
    assert re.findall(_MODEL, "uses gemini-3-pro today", re.I) == ["gemini-3-pro"]
