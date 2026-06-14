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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, _read_index(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
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
