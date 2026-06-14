"""Planning Copilot — natural-language front end over the deterministic engine.

It drives the DYNAMIC WORKFLOW: while the profile is incomplete it asks the next
adaptive interview question; once complete it runs the orchestrator and narrates
the result. Every reply is passed through the guard, so the copilot can phrase but
never invent a number.

Two modes:
  * deterministic (no ``llm``): the user's input answers the current question; the
    interview state machine decides what's next. Fully reproducible — used in tests
    and as a zero-dependency demo.
  * LLM (``llm`` callable): a bounded tool-calling loop where the model chooses
    tools from the catalog; tool outputs are real engine Results and the final
    reply is guarded against them.
"""
from __future__ import annotations

import json
from datetime import date

from ..explain.guard import validate
from ..explain.renderer import render_plain
from ..interview.statemachine import next_question
from .engine_tools import call_tool, tool_catalog

_MAX_TOOL_CALLS = 8


def _coerce(value, qtype):
    if qtype == "boolean":
        return value if isinstance(value, bool) else str(value).strip().lower() in ("true", "yes", "y", "1")
    if qtype == "integer":
        return int(float(value))
    if qtype == "number":
        return float(value)
    return value  # choice / string


def _set_path(obj: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = obj
    for seg in parts[:-1]:
        if not isinstance(cur.get(seg), dict):
            cur[seg] = {}
        cur = cur[seg]
    cur[parts[-1]] = value


def start(profile: dict | None = None, as_of: str | None = None) -> dict:
    """Initialize copilot state."""
    p = dict(profile or {})
    p.setdefault("schema_version", "1.0.0")
    if as_of:
        p.setdefault("as_of", as_of)
    return {"profile": p, "history": []}


def turn(state: dict, user_input=None, *, llm=None, as_of: str | None = None,
         seed: int | None = None, trials: int | None = None) -> dict:
    """Advance one conversational turn. Returns reply + updated state + status."""
    profile = dict(state.get("profile") or {})
    profile.setdefault("schema_version", "1.0.0")
    if as_of and not profile.get("as_of"):
        profile["as_of"] = as_of
    if not profile.get("as_of"):
        profile["as_of"] = date.today().isoformat()  # noqa: P0-CLOCK  (I/O boundary: defaults as_of; engine never reads the clock)
    history = list(state.get("history") or [])
    if user_input is not None:
        history.append({"role": "user", "content": str(user_input)})

    if llm is not None:
        out = _llm_turn(profile, history, llm, seed, trials)
        out["llm_used"] = True   # reached only if the LLM path ran to a reply (D2)
        return out
    out = _deterministic_turn(profile, history, user_input, seed, trials)
    out["llm_used"] = False
    return out


# --------------------------------------------------------------------------- #
# Deterministic mode — the dynamic interview, conversationalized.
# --------------------------------------------------------------------------- #
def _deterministic_turn(profile, history, user_input, seed, trials) -> dict:
    q = next_question(profile)
    if q is not None and user_input is not None:
        value = _coerce(user_input, q.get("type", "string"))
        # B15: validate a choice answer against its allowed set BEFORE storing — never
        # accept free text (e.g. "<script>") as an enum value. Re-ask on a bad choice.
        if q.get("type") == "choice" and q.get("choices") and value not in q["choices"]:
            reply = f"Please choose one of: {', '.join(q['choices'])}."
            history.append({"role": "assistant", "content": reply})
            return {"status": "collecting", "reply": reply, "next_question": q,
                    "state": {"profile": profile, "history": history}, "tool_results": []}
        _set_path(profile, q["field"], value)
        q = next_question(profile)

    if q is not None:
        reply = q["prompt"]
        history.append({"role": "assistant", "content": reply})
        return {"status": "collecting", "reply": reply, "next_question": q,
                "state": {"profile": profile, "history": history}, "tool_results": []}

    tr = call_tool("workflow_run", {"profile": profile, "as_of": profile.get("as_of"),
                                    "seed": seed, "trials": trials})
    result = tr["output"]
    reply = validate(render_plain(result), result)        # guarded narration
    history.append({"role": "assistant", "content": reply})
    return {"status": "ready", "reply": reply, "result": result,
            "state": {"profile": profile, "history": history}, "tool_results": [tr]}


# --------------------------------------------------------------------------- #
# LLM mode — bounded tool-calling loop, guarded final answer.
# --------------------------------------------------------------------------- #
_SYSTEM = (
    "You are a financial planning copilot. You may ONLY obtain facts by calling the "
    "provided tools; never state a dollar amount, percentage, or age that did not "
    "come from a tool result. Respond ONLY with JSON: either "
    '{"tool": "<name>", "args": {...}} to call a tool, or '
    '{"final": "<reply to the user>"} when done. '
    "When the user states a fact (age, income, state, filing status, expenses, accounts), "
    'FIRST call set_profile_fields with {"<dotted.path>": value} to record it (the profile '
    "passed back reflects what is stored). Then call workflow_run for the next question to "
    "ask, or the finished plan once enough is known."
)


def _build_prompt(profile, history, tool_results) -> str:
    return json.dumps({
        "system": _SYSTEM,
        "tools": tool_catalog(),
        "profile": profile,
        "history": history,
        "tool_results_so_far": [{"tool": t["tool"], "output": t["output"]} for t in tool_results],
    }, default=str)


def _plan_result(tool_results):
    """The most recent tool output that is a full plan (for the SPA to render)."""
    for tr in reversed(tool_results):
        out = tr.get("output")
        if isinstance(out, dict) and ("recommendations" in out or out.get("status") == "ready"):
            return out
    return None


def _llm_turn(profile, history, llm, seed, trials) -> dict:
    tool_results: list[dict] = []
    for _ in range(_MAX_TOOL_CALLS):
        raw = llm(_build_prompt(profile, history, tool_results))
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Treat unparseable output as a final reply and guard it.
            reply = validate(str(raw), [t["output"] for t in tool_results] or [{}])
            history.append({"role": "assistant", "content": reply})
            return {"status": "ready", "reply": reply, "result": _plan_result(tool_results),
                    "tool_results": tool_results, "state": {"profile": profile, "history": history}}
        if "tool" in msg:
            args = msg.get("args", {}) or {}
            args["profile"] = profile                      # always the CURRENT (threaded) profile
            args.setdefault("as_of", profile.get("as_of"))
            if seed is not None:
                args.setdefault("seed", seed)
            if trials is not None:
                args.setdefault("trials", trials)
            tr = call_tool(msg["tool"], args)
            tool_results.append(tr)
            out = tr.get("output")
            if isinstance(out, dict) and isinstance(out.get("profile"), dict):
                profile = out["profile"]                   # thread the UPDATED profile forward (D6/B1)
            continue
        # final answer — guard against every tool output gathered this turn
        reply = validate(str(msg.get("final", "")), [t["output"] for t in tool_results] or [{}])
        history.append({"role": "assistant", "content": reply})
        return {"status": "ready", "reply": reply, "result": _plan_result(tool_results),
                "tool_results": tool_results, "state": {"profile": profile, "history": history}}

    # Loop budget exhausted: NEVER raise (no HTTP 500). Hand back to the deterministic
    # path — it asks the next question, or runs the plan if the profile is complete (D6).
    return _deterministic_turn(profile, history, None, seed, trials)
