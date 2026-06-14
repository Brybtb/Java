"""The Tool/Contract plane — the ONLY door an agent may use to reach the engine.

Each tool wraps a pure engine function, validates typed args, and returns a
``ToolResult``: the engine output plus a determinism stamp (engine version + a
content hash of the output). Agents call tools through :func:`call_tool`; they may
NOT import calculators or do arithmetic that lands in output. This is what lets a
non-deterministic LLM drive the system while every number stays provably from the
deterministic core.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date

from jsonschema import Draft7Validator

from .. import full_plan, plan as _plan
from ..montecarlo import run as _mc
from ..optimize.estate import analyze as _estate
from ..optimize.risk import analyze as _risk
from ..optimize.roth_conversion import conversion_analysis as _roth
from ..optimize.social_security import claiming_analysis as _ss
from ..optimize.withdrawal_plan import withdrawal_plan as _withdraw
from ..projection import project as _project
from ..rules.loader import load_params
from ..interview.statemachine import _questions, next_question, remaining
from ..version import DEFAULT_MC_SEED, DEFAULT_MC_TRIALS, __version__
from ..workflow.orchestrator import run as _workflow
from ..schemas.validate import _load_schema
from ..engine.errors import ProfileError


def _as_of(args: dict) -> date:
    raw = args.get("as_of") or args.get("profile", {}).get("as_of")
    if not raw:
        raise ValueError("as_of required (pass it or include profile.as_of)")
    return raw if isinstance(raw, date) else date.fromisoformat(str(raw))


def _stamp(name: str, output) -> dict:
    blob = json.dumps(output, sort_keys=True, default=str).encode("utf-8")
    return {
        "tool": name,
        "engine_version": __version__,
        "output_hash": "sha256:" + hashlib.sha256(blob).hexdigest(),
        "output": output,
    }


# --- tool implementations (each takes one args dict) ----------------------- #
def _t_workflow(a):
    return _workflow(a["profile"], a.get("as_of"),
                     seed=a.get("seed"), trials=a.get("trials"))


def _t_plan(a):
    return _plan(a["profile"], a.get("as_of"))


def _t_full_plan(a):
    return full_plan(a["profile"], a.get("as_of"),
                     seed=a.get("seed", DEFAULT_MC_SEED),
                     trials=a.get("trials", DEFAULT_MC_TRIALS))


def _t_project(a):
    return _project(a["profile"], _as_of(a))


def _t_montecarlo(a):
    return _mc(a["profile"], _as_of(a), seed=a.get("seed", DEFAULT_MC_SEED),
               trials=a.get("trials", DEFAULT_MC_TRIALS),
               return_model=a.get("return_model", "normal"))


def _t_estate(a):
    p = a["profile"]
    d = _as_of(a)
    return _estate(p, load_params(d, p["household"]["state"]), d)


def _t_risk(a):
    return _risk(a["profile"], a.get("projection"))


def _t_roth(a):
    p = a["profile"]
    d = _as_of(a)
    return _roth(p, load_params(d, p["household"]["state"]), d)


def _t_social_security(a):
    return _ss(a["pia_monthly"], a.get("fra_age", 67.0), a.get("longevity_age", 90))


def _t_withdraw(a):
    return _withdraw(a["profile"], a.get("annual_need"))


def _t_interview_next(a):
    p = a["profile"]
    q = next_question(p)
    return {"next_question": q, "remaining": remaining(p), "complete": q is None}


def _qmap() -> dict:
    return {q["field"]: q for q in _questions()}


def _set_path(obj: dict, path: str, value) -> None:
    cur = obj
    parts = path.split(".")
    for seg in parts[:-1]:
        if not isinstance(cur.get(seg), dict):
            cur[seg] = {}
        cur = cur[seg]
    cur[parts[-1]] = value


def _coerce(value, qtype):
    if qtype == "boolean":
        return value if isinstance(value, bool) else str(value).strip().lower() in ("true", "yes", "y", "1")
    if qtype == "integer":
        return int(float(value))
    if qtype == "number":
        return float(value)
    return value


def _reject_invalid_values(profile: dict) -> None:
    """Reject present-but-invalid VALUES (bad enum/type/pattern) while ignoring
    missing-field 'required' errors, so the copilot can keep building a partial profile."""
    bad = [e for e in Draft7Validator(_load_schema("profile.schema.json")).iter_errors(profile)
           if e.validator != "required"]
    if bad:
        loc = "/".join(str(p) for p in bad[0].path) or "(root)"
        raise ProfileError(f"invalid value at {loc}: {bad[0].message}")


def _t_set_profile_fields(a):
    """Store the user's stated facts: coerce each value by its interview question type,
    reject invalid values, and return the UPDATED profile (used on the next turn).
    The only way the copilot records what the user said before running the plan (D6/B1)."""
    fields = a.get("fields") or {}
    if not isinstance(fields, dict):
        raise ValueError("fields must be an object of {dotted_path: value}")
    qmap = _qmap()
    p = copy.deepcopy(a.get("profile") or {})
    p.setdefault("schema_version", "1.0.0")
    applied = {}
    for path, value in fields.items():
        q = qmap.get(path)
        coerced = _coerce(value, q["type"]) if q else value
        if q and q.get("type") == "choice" and q.get("choices") and coerced not in q["choices"]:
            raise ProfileError(f"invalid choice for {path}: {coerced!r} not in {q['choices']}")
        _set_path(p, path, coerced)
        applied[path] = coerced
    _reject_invalid_values(p)
    return {"profile": p, "applied": applied, "remaining": remaining(p),
            "complete": next_question(p) is None}


# name -> (description, JSON-schema params, fn)
TOOLS: dict[str, dict] = {
    "workflow_run": {
        "description": "Run the dynamic planning workflow: returns the next interview "
                       "question while data is incomplete, or the full plan + selected "
                       "modules + optimizers once ready. Preferred entry point.",
        "parameters": {"type": "object",
                       "properties": {"profile": {"type": "object"},
                                      "as_of": {"type": "string"},
                                      "seed": {"type": "integer"},
                                      "trials": {"type": "integer"}},
                       "required": ["profile"]},
        "fn": _t_workflow},
    "plan": {"description": "Financial Order of Operations recommendations + audit trace.",
             "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                            "as_of": {"type": "string"}}, "required": ["profile"]},
             "fn": _t_plan},
    "full_plan": {"description": "Plan + projection + Monte Carlo + insights.",
                  "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                                 "as_of": {"type": "string"}, "seed": {"type": "integer"},
                                 "trials": {"type": "integer"}}, "required": ["profile"]},
                  "fn": _t_full_plan},
    "project": {"description": "Deterministic multi-year retirement projection.",
                "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                               "as_of": {"type": "string"}}, "required": ["profile"]},
                "fn": _t_project},
    "montecarlo": {"description": "Seeded Monte Carlo probability of success.",
                   "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                                  "as_of": {"type": "string"}, "seed": {"type": "integer"},
                                  "trials": {"type": "integer"},
                                  "return_model": {"type": "string", "enum": ["normal", "t"]}},
                                  "required": ["profile"]},
                   "fn": _t_montecarlo},
    "estate": {"description": "Estate-tax projection + transfer-strategy modeling.",
               "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                              "as_of": {"type": "string"}}, "required": ["profile"]},
               "fn": _t_estate},
    "risk": {"description": "Risk capacity vs tolerance, alignment, and stress tests.",
             "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                            "projection": {"type": "object"}}, "required": ["profile"]},
             "fn": _t_risk},
    "roth": {"description": "Roth-conversion / bracket-fill targets.",
             "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                            "as_of": {"type": "string"}}, "required": ["profile"]},
             "fn": _t_roth},
    "social_security": {"description": "Social Security claiming-age optimization.",
                        "parameters": {"type": "object",
                                       "properties": {"pia_monthly": {"type": "number"},
                                                      "fra_age": {"type": "number"},
                                                      "longevity_age": {"type": "integer"}},
                                       "required": ["pia_monthly"]},
                        "fn": _t_social_security},
    "withdraw": {"description": "Tax-efficient withdrawal sequencing.",
                 "parameters": {"type": "object", "properties": {"profile": {"type": "object"},
                                "annual_need": {"type": "number"}}, "required": ["profile"]},
                 "fn": _t_withdraw},
    "interview_next": {"description": "Next guided-interview question for a partial profile.",
                       "parameters": {"type": "object", "properties": {"profile": {"type": "object"}},
                                      "required": ["profile"]},
                       "fn": _t_interview_next},
    "set_profile_fields": {
        "description": "Store the user's stated facts into the profile: coerces each value by its "
                       "interview question type, rejects invalid values, and returns the UPDATED "
                       "profile (use it on the next turn). The ONLY way to record what the user "
                       "said before running the plan. Call this whenever the user provides a fact.",
        "parameters": {"type": "object",
                       "properties": {"profile": {"type": "object"},
                                      "fields": {"type": "object",
                                                 "description": "{dotted.path: value}, e.g. {\"household.state\": \"TX\", \"household.primary_age\": 40}"}},
                       "required": ["profile", "fields"]},
        "fn": _t_set_profile_fields},
}


def tool_catalog() -> list[dict]:
    """The catalog an LLM is given — names, descriptions, and arg schemas only."""
    return [{"name": n, "description": t["description"], "parameters": t["parameters"]}
            for n, t in TOOLS.items()]


def call_tool(name: str, args: dict) -> dict:
    """Run a tool and return a stamped ToolResult. Raises on unknown tool."""
    tool = TOOLS.get(name)
    if tool is None:
        raise KeyError(f"unknown tool {name!r}; available: {sorted(TOOLS)}")
    return _stamp(name, tool["fn"](args or {}))
