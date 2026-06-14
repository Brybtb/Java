#!/usr/bin/env python3
"""Dependency-free web UI for the deterministic financial planning agent.

Uses only the Python standard library (http.server) so it runs with no extra
install. The engine stays deterministic; this layer is pure I/O.

Endpoints:
  GET  /                 -> the dynamic-workflow single-page app
  POST /api/workflow     -> {profile, as_of?, seed?, trials?} -> orchestrator result
                            (next question while collecting, or the full plan when ready)
  POST /api/report.pdf   -> {profile, as_of?} -> white-labeled PDF bytes

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

_HERE = os.path.dirname(__file__)


def _read_index() -> bytes:
    with open(os.path.join(_HERE, "index.html"), "rb") as f:
        return f.read()


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

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        try:
            data = self._body()
            profile = data.get("profile", {})
            as_of = data.get("as_of") or profile.get("as_of")
            if self.path == "/api/copilot/turn":
                from foo_agent.agents.copilot import turn, start
                llm = None
                if data.get("llm"):
                    from foo_agent.agents.llm import get_default_llm
                    llm = get_default_llm()  # None if no provider key in the server env
                state = data.get("state") or start(data.get("profile"), as_of)
                out = turn(state, data.get("message"), llm=llm, as_of=as_of,
                           seed=data.get("seed"), trials=data.get("trials") or 2000)
                out["llm_active"] = llm is not None
                self._send(200, json.dumps(out, default=str).encode(), "application/json")
            elif self.path == "/api/workflow":
                from foo_agent.workflow.orchestrator import run
                result = run(profile, as_of,
                             seed=data.get("seed"), trials=data.get("trials") or 2000)
                self._send(200, json.dumps(result, default=str).encode(), "application/json")
            elif self.path == "/api/report.pdf":
                from foo_agent.workflow.orchestrator import run
                from foo_agent.report.pdf import render_pdf_bytes
                from foo_agent.report.branding import Branding
                result = run(profile, as_of, trials=data.get("trials") or 4000)
                if result.get("status") != "ready":
                    self._send(400, json.dumps(result, default=str).encode(), "application/json")
                    return
                pdf = render_pdf_bytes(result, Branding(), profile=profile)
                self._send(200, pdf, "application/pdf")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:  # surface errors as JSON for the SPA
            self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")


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
