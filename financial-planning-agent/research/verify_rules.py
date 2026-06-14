#!/usr/bin/env python3
"""
Financial Planning Agent — Rule Verification (Parallel.ai Task API)
==================================================================
Mirrors ../../wealth-ai-workflow/verify_claims.py. Each load-bearing FOO rule is
turned into a CLAIM and independently re-researched via the Task API, which
returns a structured verdict + basis citations. Verdicts are written back so each
rule's `verification` block reflects current primary-source support.

The claims are built dynamically from the live ruleset, so this stays in sync as
rules are added.

Usage:
    export PARALLEL_API_KEY=sk-...
    python3 verify_rules.py --dry-run
    python3 verify_rules.py --processor core
Output (./output): verification_<ts>.json, verification_latest.json, verification_report.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# Import the live ruleset so claims track the rules exactly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from foo_agent.rules.loader import load_ruleset  # noqa: E402

RUNS_URL = "https://api.parallel.ai/v1/tasks/runs"
TIMEOUT, RESULT_TIMEOUT, MAX_RETRIES = 60, 300, 4

OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string",
                        "enum": ["supported", "partially_supported", "unsupported", "contradicted"]},
            "best_practice_note": {"type": "string"},
            "primary_source": {"type": "string"},
            "source_type": {"type": "string", "enum": ["primary", "trade_press", "vendor", "unknown"]},
            "notes": {"type": "string"},
        },
        "required": ["verdict", "best_practice_note", "primary_source", "source_type", "notes"],
        "additionalProperties": False,
    },
}

PROMPT = (
    "You are a financial-planning fact-checker representing a syndicate of CFP, "
    "CFA, tax attorney, and enrolled-agent reviewers. Assess whether the following "
    "general financial-planning RULE reflects current best practice and primary-"
    "source guidance (IRS, SSA, DOL, CFPB, CFP Board). Be strict: if the rule is "
    "directionally right but the threshold/limit is dated or nuanced, mark "
    "partially_supported and explain in notes.\n\n"
    "RULE: {title}\n"
    "RATIONALE: {rationale}\n"
    "ASSUMPTIONS: {assumptions}\n"
    "DISCIPLINES: {disciplines}"
)

BADGE = {"supported": "✅", "partially_supported": "🟡", "unsupported": "⚠️", "contradicted": "❌"}


def _redacted(k): return "<missing>" if not k else f"set (len={len(k)}, ****{k[-2:]})"


def create_run(prompt, processor, key):
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    body = {"input": prompt, "processor": processor, "task_spec": {"output_schema": OUTPUT_SCHEMA}}
    delay = 2
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(RUNS_URL, headers=headers, json=body, timeout=TIMEOUT)
            if r.status_code in (200, 202):
                return r.json()["run_id"]
            if r.status_code not in (429, 500, 502, 503, 504):
                raise SystemExit(f"Non-retryable HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            print(f"   create retry {attempt} ({e})", file=sys.stderr)
        time.sleep(delay); delay *= 2
    raise SystemExit("create_run failed")


def get_result(run_id, key):
    headers = {"x-api-key": key}
    url = f"{RUNS_URL}/{run_id}/result"
    delay = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=headers, timeout=RESULT_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                raise SystemExit(f"Non-retryable HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            print(f"   result retry {attempt} ({e})", file=sys.stderr)
        time.sleep(delay); delay *= 2
    raise SystemExit("get_result failed")


def main():
    ap = argparse.ArgumentParser(description="Verify FOO rules via Parallel Task API")
    ap.add_argument("--processor", default="base", help="lite|base|core|pro")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()

    rs = load_ruleset()
    key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[verify_rules] PARALLEL_API_KEY: {_redacted(key)}  rules={len(rs.rules)}  processor={args.processor}")

    if args.dry_run:
        for rule in rs.rules:
            print(f"  - {rule['id']}: {rule['title']}")
        return
    if not key:
        raise SystemExit("PARALLEL_API_KEY not set.")

    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    pending = []
    for rule in rs.rules:
        prompt = PROMPT.format(
            title=rule["title"], rationale=rule.get("rationale_key", ""),
            assumptions="; ".join(rule.get("assumptions", [])) or "none",
            disciplines=", ".join(rule.get("discipline", [])),
        )
        rid = create_run(prompt, args.processor, key)
        print(f"[verify_rules] queued {rule['id']} -> {rid}")
        pending.append((rule, rid))
        time.sleep(0.5)

    results = []
    for rule, rid in pending:
        res = get_result(rid, key)
        out = res.get("output", {}) or {}
        content = out.get("content", {}) if isinstance(out, dict) else {}
        results.append({
            "rule_id": rule["id"], "title": rule["title"], "run_id": rid,
            "verdict": content.get("verdict"), "best_practice_note": content.get("best_practice_note"),
            "primary_source": content.get("primary_source"), "source_type": content.get("source_type"),
            "notes": content.get("notes"), "basis": out.get("basis", []),
        })

    payload = {"generated_utc": ts, "processor": args.processor, "results": results}
    for name in (f"verification_{ts}.json", "verification_latest.json"):
        with open(os.path.join(args.outdir, name), "w") as f:
            json.dump(payload, f, indent=2)

    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    lines = ["# FOO Rule Verification Report", "",
             f"Generated {ts[:4]}-{ts[4:6]}-{ts[6:8]} via Parallel.ai Task API (processor `{args.processor}`).", "",
             "| Verdict | Count |", "|---|---|"]
    for v, n in counts.items():
        lines.append(f"| {BADGE.get(v, '?')} {v} | {n} |")
    lines += ["", "## Rule-by-rule", ""]
    for r in results:
        lines += [f"### {BADGE.get(r['verdict'],'?')} {r['rule_id']} — {r['title']}", "",
                  f"- **Verdict:** {r['verdict']}",
                  f"- **Best-practice note:** {r['best_practice_note'] or '—'}",
                  f"- **Most authoritative source:** {r['primary_source'] or '—'} _({r['source_type'] or 'unknown'})_",
                  f"- **Notes:** {r['notes'] or '—'}", ""]
    lines += ["---", "> [!warning] Disclosure",
              "> AI-assisted verification with human review required. Confirm each figure "
              "against the linked primary source before relying on it."]
    with open(os.path.join(args.outdir, "verification_report.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"[verify_rules] DONE. verdicts={counts}")


if __name__ == "__main__":
    main()
