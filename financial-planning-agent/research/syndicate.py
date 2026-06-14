#!/usr/bin/env python3
"""
Financial Planning Agent — Syndicate Cross-Validation (Parallel.ai Task API)
===========================================================================
Mirrors ../../finlink-ria-ma-intelligence/deep_research.py (Layer B). Asks the
Task API to play each professional lens and CROSS-VALIDATE the canonical FOO
ordering — surfacing any discipline-specific disagreement (e.g. a tax attorney
preferring HSA before debt for a specific client, or an estate attorney flagging
beneficiary review earlier). Output is an advisory cross-check, not a rule change.

Usage:
    export PARALLEL_API_KEY=sk-...
    python3 syndicate.py --dry-run
    python3 syndicate.py --processor core
Output (./output): syndicate_<ts>.json, syndicate_latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

RUNS_URL = "https://api.parallel.ai/v1/tasks/runs"
TIMEOUT, RESULT_TIMEOUT, RETRIES = 60, 360, 4

SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "agrees_with_ordering": {"type": "boolean"},
            "concerns": {"type": "array", "items": {"type": "string"}},
            "exceptions": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["agrees_with_ordering", "concerns", "exceptions", "confidence"],
        "additionalProperties": False,
    },
}

FOO = (
    "1) starter emergency buffer, 2) capture full employer match, 3) pay high-"
    "interest debt, 4) full 3-6 month reserve, 5) max HSA, 6) max IRA, 7) max "
    "employer plan, 8) taxable brokerage, 9) protection/estate review"
)

LENSES = ["CFP", "CFA", "tax attorney", "estate attorney", "insurance specialist",
          "banking/lending specialist", "mortgage specialist", "enrolled agent / CPA",
          "Social Security / Medicare specialist", "student-loan specialist",
          "behavioral-finance specialist"]


def _redacted(k): return "<missing>" if not k else f"set(len={len(k)},****{k[-2:]})"


def task_create(prompt, processor, key):
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
            print(f"   create retry {a} ({e})", file=sys.stderr)
        time.sleep(d); d *= 2
    raise SystemExit("task create failed")


def task_result(run_id, key):
    h = {"x-api-key": key}; url = f"{RUNS_URL}/{run_id}/result"; d = 3
    for a in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=h, timeout=RESULT_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            print(f"   result retry {a} ({e})", file=sys.stderr)
        time.sleep(d); d *= 2
    raise SystemExit("task result failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processor", default="core")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()
    key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[syndicate] PARALLEL_API_KEY: {_redacted(key)}  lenses={len(LENSES)}")
    if args.dry_run:
        for l in LENSES:
            print("  lens:", l)
        return
    if not key:
        raise SystemExit("PARALLEL_API_KEY not set.")

    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    pending = []
    for lens in LENSES:
        prompt = (
            f"Acting strictly as a {lens}, review this general Financial Order of "
            f"Operations for a typical US household: {FOO}. Based on current best "
            f"practice and primary-source guidance, do you AGREE with this default "
            f"ordering? List specific concerns and the client situations that would "
            f"justify an EXCEPTION to it. Be objective and concrete."
        )
        rid = task_create(prompt, args.processor, key)
        print(f"[syndicate] queued {lens} -> {rid}")
        pending.append((lens, rid))
        time.sleep(0.5)

    results = []
    for lens, rid in pending:
        rj = task_result(rid, key); out = rj.get("output", {}) or {}
        results.append({"lens": lens, "run_id": rid,
                        "content": out.get("content", {}), "basis": out.get("basis", [])})

    for name in (f"syndicate_{ts}.json", "syndicate_latest.json"):
        with open(os.path.join(args.outdir, name), "w") as f:
            json.dump({"generated_utc": ts, "foo": FOO, "results": results}, f, indent=2)

    agree = sum(1 for r in results if (r["content"] or {}).get("agrees_with_ordering"))
    print(f"[syndicate] DONE. {agree}/{len(results)} lenses agree with default ordering.")


if __name__ == "__main__":
    main()
