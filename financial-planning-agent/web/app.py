#!/usr/bin/env python3
"""Dependency-free web UI for the deterministic financial planning agent.

Uses only the Python standard library (http.server) so it runs with no extra
install. The engine stays deterministic; this layer is pure I/O.

Request handling is split into a pure ``handle_post(path, raw_bytes) -> (code,
body, ctype)`` so error mapping is unit-testable without a live server (C00).

Endpoints:
  GET  /                 -> the dynamic-workflow single-page app
  POST /api/copilot/turn -> chat turn over the dynamic workflow
  POST /api/workflow     -> orchestrator result (next question or full plan)
  POST /api/report.pdf   -> white-labeled PDF bytes

Run:
    PYTHONPATH=. python3 web/app.py [--port 8765]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from foo_agent.engine.errors import (  # noqa: E402
    AssumptionError, ConditionError, ProfileError, RuleError,
)

_HERE = os.path.dirname(__file__)

# Input-driven failures -> 400 (the client can fix them). Their messages describe
# the submitted profile, so they are safe to echo. Everything else (incl.
# DeterminismError, GuardError, unexpected faults) -> 500 with a sanitized body.
_CLIENT_ERRORS = (ProfileError, AssumptionError, RuleError, ConditionError,
                  ValueError, TypeError, KeyError)


class _BadRequest(Exception):
    """A malformed request the client must fix (-> HTTP 400)."""


def _validate_if_complete(profile: dict) -> None:
    """Reject present-but-invalid field VALUES (bad enum, wrong type, bad pattern)
    at the boundary -> 400, while IGNORING missing-field ('required') errors so the
    interview can still collect a partial profile. A complete-but-invalid submission
    no longer slips through as a degenerate plan or a 500 (B10)."""
    if not profile:
        return
    from jsonschema import Draft7Validator

    from foo_agent.engine.errors import ProfileError
    from foo_agent.schemas.validate import _load_schema

    validator = Draft7Validator(_load_schema("profile.schema.json"))
    bad = [e for e in validator.iter_errors(profile) if e.validator != "required"]
    if bad:
        loc = "/".join(str(p) for p in bad[0].path) or "(root)"
        raise ProfileError(f"invalid value at {loc}: {bad[0].message}")


def _intake_brackets(filing_status: str, as_of) -> dict:
    """Income-band pills (C05 / NOTE-1): turn the federal marginal brackets for the
    chosen filing status into GROSS-income bands and tag each with its marginal rate.

    A bracket threshold is on TAXABLE income; the intake question asks for GROSS
    income, so each edge is shifted up by that status's standard deduction
    (gross = taxable + standard_deduction). Federal brackets are state-independent,
    so we resolve params through the normal dated loader (any valid state works) —
    the numbers stay engine-sourced, never hand-typed in the UI."""
    from foo_agent.interview.statemachine import _questions
    from foo_agent.rules.loader import load_params

    statuses = next((q["choices"] for q in _questions() if q["id"] == "filing_status"), [])
    if filing_status not in statuses:
        raise ProfileError(f"unknown filing_status {filing_status!r}; choose one of {statuses}")
    d = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))
    tax = load_params(d, "TX")["tax"]               # TX overlay has no income tax; brackets are federal
    ded = tax["standard_deduction"][filing_status]
    bands, lower = [], 0
    for b in tax["brackets"][filing_status]:
        up = b.get("up_to")
        upper = (up + ded) if up is not None else None
        value = round((lower + upper) / 2) if upper is not None else lower
        label = f"${lower:,.0f}–${upper:,.0f}" if upper is not None else f"${lower:,.0f}+"
        bands.append({"rate": b["rate"], "marginal_rate_pct": round(b["rate"] * 100),
                      "lower": lower, "upper": upper, "value": value, "label": label})
        lower = upper if upper is not None else lower
    return {"filing_status": filing_status, "as_of": d.isoformat(),
            "standard_deduction": ded, "bands": bands}


def _read_index() -> bytes:
    with open(os.path.join(_HERE, "index.html"), "rb") as f:
        return f.read()


def _json(code: int, obj) -> tuple[int, bytes, str]:
    return code, json.dumps(obj, default=str).encode(), "application/json"


def _parse_body(raw: bytes) -> dict:
    def _reject_constant(_):  # B11: NaN / Infinity / -Infinity are not valid input
        raise _BadRequest("non-finite numbers (NaN/Infinity) are not allowed")
    try:
        data = json.loads(raw or b"{}", parse_constant=_reject_constant)
    except _BadRequest:
        raise
    except (json.JSONDecodeError, ValueError):
        raise _BadRequest("request body is not valid JSON")
    if not isinstance(data, dict):
        raise _BadRequest("request body must be a JSON object")
    return data


def dispatch(path: str, data: dict) -> tuple[int, bytes, str]:
    profile = data.get("profile") or {}                  # B13: null profile -> {}
    as_of = data.get("as_of") or profile.get("as_of")
    if path == "/api/copilot/turn":
        from foo_agent.agents.copilot import start, turn
        llm = None
        if data.get("llm"):
            from foo_agent.agents.llm import get_default_llm
            llm = get_default_llm()  # None if no provider key in the server env
        state = data.get("state") or start(data.get("profile") or {}, as_of)
        out = turn(state, data.get("message"), llm=llm, as_of=as_of,
                   seed=data.get("seed"), trials=data.get("trials") or 2000)
        out["llm_active"] = bool(out.get("llm_used"))     # D2: honest — only if the LLM ran this turn
        return _json(200, out)
    if path == "/api/workflow":
        from foo_agent.workflow.orchestrator import run
        _validate_if_complete(profile)
        return _json(200, run(profile, as_of, seed=data.get("seed"),
                              trials=data.get("trials") or 2000))
    if path == "/api/report.pdf":
        from foo_agent.report.branding import Branding
        from foo_agent.report.pdf import render_pdf_bytes
        from foo_agent.workflow.orchestrator import run
        _validate_if_complete(profile)
        result = run(profile, as_of, trials=data.get("trials") or 4000)
        if result.get("status") != "ready":
            return _json(400, result)
        return 200, render_pdf_bytes(result, Branding(), profile=profile), "application/pdf"
    return 404, b"not found", "text/plain"


def handle_post(path: str, raw: bytes) -> tuple[int, bytes, str]:
    try:
        return dispatch(path, _parse_body(raw))
    except _BadRequest as e:
        return _json(400, {"error": str(e)})
    except _CLIENT_ERRORS as e:                            # B10: input errors -> 400
        return _json(400, {"error": str(e)})
    except Exception:                                      # D3: never leak raw fault text
        return _json(500, {"error": "internal error"})


def handle_get(path: str, query: str) -> tuple[int, bytes, str]:
    """Pure GET dispatch (unit-testable). Same error mapping as handle_post:
    bad/invalid input -> 400, unknown path -> 404, unexpected fault -> sanitized 500."""
    try:
        if path == "/favicon.ico":                         # silence the browser's default fetch (no console 404)
            return 204, b"", "image/x-icon"
        if path == "/api/intake/brackets":                 # C05: income-band pills
            q = parse_qs(query or "")
            fs = (q.get("filing_status") or [None])[0]
            if not fs:
                raise _BadRequest("filing_status query parameter is required")
            as_of = (q.get("as_of") or [None])[0] or date.today().isoformat()  # noqa: P0-CLOCK (I/O boundary)
            return _json(200, _intake_brackets(fs, as_of))
        return 404, b"not found", "text/plain"
    except _BadRequest as e:
        return _json(400, {"error": str(e)})
    except _CLIENT_ERRORS as e:
        return _json(400, {"error": str(e)})
    except Exception:
        return _json(500, {"error": "internal error"})


_MAX_CONTENT = 1_000_000   # B9: cap request body (~1 MB) — bound memory, reject oversize


class Handler(BaseHTTPRequestHandler):
    timeout = 30           # B9: socket timeout defeats slowloris — a stalled client can't hang a worker

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path in ("/", "/index.html"):
            self._send(200, _read_index(), "text/html; charset=utf-8")
        else:
            self._send(*handle_get(parts.path, parts.query))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > _MAX_CONTENT:                                   # B9: reject oversize before reading
            self._send(*_json(413, {"error": "request entity too large"}))
            return
        raw = self.rfile.read(n) if n else b""
        self._send(*handle_post(self.path, raw))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="foo-agent web UI")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[foo-agent web] serving on http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
