#!/usr/bin/env python3
"""
Financial Planning Agent — Assumption Verification (Parallel.ai Task API)
========================================================================
Verifies the dated dollar PARAMETERS the engine relies on (contribution limits,
phase-outs, standard deductions) against IRS/SSA primary sources for a given tax
year. Run this whenever the year rolls over or new IRS figures publish, then
update foo_agent/rules/data/jurisdiction/_us_federal.params.yaml.

Mirrors the verify_claims.py Task-API pattern. Reads the live params file so the
claims always match what the engine actually uses.

Usage:
    export PARALLEL_API_KEY=sk-...
    python3 verify_assumptions.py --year 2026 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from foo_agent.rules.loader import load_params  # noqa: E402

RUNS_URL = "https://api.parallel.ai/v1/tasks/runs"
TIMEOUT, RESULT_TIMEOUT, RETRIES = 60, 300, 4

SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "matches": {"type": "string", "enum": ["yes", "no", "unclear"]},
            "correct_value": {"type": "string"},
            "primary_source": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["matches", "correct_value", "primary_source", "notes"],
        "additionalProperties": False,
    },
}


def _redacted(k): return "<missing>" if not k else f"set(len={len(k)},****{k[-2:]})"


def _claims_from_params(params: dict, year: int) -> list[dict]:
    cl = params.get("contribution_limits", {})
    out = [
        {"id": "elective_deferral",
         "q": f"For tax year {year}, what is the IRS 401(k)/403(b) employee elective "
              f"deferral limit (402(g))? The engine uses {cl.get('elective_deferral', {}).get('limit')}."},
        {"id": "ira_limit",
         "q": f"For tax year {year}, what is the IRS traditional/Roth IRA contribution "
              f"limit (under age 50)? The engine uses {cl.get('ira', {}).get('limit')}."},
        {"id": "hsa_family",
         "q": f"For tax year {year}, what is the IRS HSA family contribution limit? "
              f"The engine uses {cl.get('hsa', {}).get('family')}."},
    ]
    return out


def _run(prompt, key, processor):
    h = {"x-api-key": key, "Content-Type": "application/json"}
    body = {"input": prompt, "processor": processor, "task_spec": {"output_schema": SCHEMA}}
    d = 2
    for a in range(1, RETRIES + 1):
        try:
            r = requests.post(RUNS_URL, headers=h, json=body, timeout=TIMEOUT)
            if r.status_code in (200, 202):
                return r.json()["run_id"]
            if r.status_code not in (429, 500, 502, 503, 504):
                raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            print(f"   retry {a} ({e})", file=sys.stderr)
        time.sleep(d); d *= 2
    raise SystemExit("create failed")


def _result(rid, key):
    h = {"x-api-key": key}; d = 3
    for a in range(1, RETRIES + 1):
        try:
            r = requests.get(f"{RUNS_URL}/{rid}/result", headers=h, timeout=RESULT_TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException as e:
            print(f"   retry {a} ({e})", file=sys.stderr)
        time.sleep(d); d *= 2
    raise SystemExit("result failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--processor", default="base")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()

    params = load_params(date(args.year, 6, 1), "TX")
    claims = _claims_from_params(params, args.year)
    key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[verify_assumptions] PARALLEL_API_KEY: {_redacted(key)}  claims={len(claims)}  year={args.year}")
    if args.dry_run:
        for c in claims:
            print(f"  - {c['id']}: {c['q']}")
        return
    if not key:
        raise SystemExit("PARALLEL_API_KEY not set.")

    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pending = [(c, _run(c["q"], key, args.processor)) for c in claims]
    results = []
    for c, rid in pending:
        out = _result(rid, key).get("output", {}) or {}
        results.append({"id": c["id"], "question": c["q"], "run_id": rid,
                        "content": out.get("content", {}), "basis": out.get("basis", [])})
    for name in (f"assumptions_{ts}.json", "assumptions_latest.json"):
        with open(os.path.join(args.outdir, name), "w") as f:
            json.dump({"generated_utc": ts, "year": args.year, "results": results}, f, indent=2)
    mism = [r["id"] for r in results if (r["content"] or {}).get("matches") == "no"]
    print(f"[verify_assumptions] DONE. mismatches: {mism or 'none'}")


if __name__ == "__main__":
    main()
