#!/usr/bin/env python3
"""
Wealth AI — Stage 3: Claim Verification (Parallel.ai Task API)
==============================================================
Fact-checks the top statistics in the build-vs-buy briefing by running each
claim through the Parallel.ai **Task API**, which combines inference with live
web research and returns a structured `basis` (citations + reasoning +
confidence) per output field.

For each claim the Task is asked to return a strict JSON verdict:
  verdict           supported | partially_supported | unsupported | contradicted
  verified_figure   the figure the research actually supports (or "")
  primary_source    most authoritative URL found
  source_type       primary | trade_press | vendor | unknown
  notes             one-line explanation

API contract (verified live 2026-06-02):
  POST https://api.parallel.ai/v1/tasks/runs        headers: x-api-key
       body: {input, processor, task_spec:{output_schema:{type:"json",json_schema:{...}}}}
       -> 202 {run_id, status:"queued"}
  GET  https://api.parallel.ai/v1/tasks/runs/{run_id}/result   (blocks until done)
       -> {run:{status}, output:{content:{...}, basis:[{field,citations,reasoning,confidence}]}}

Usage:
    export PARALLEL_API_KEY=sk-...
    python3 verify_claims.py                 # verify all claims
    python3 verify_claims.py --processor core  # deeper (slower) research
    python3 verify_claims.py --dry-run

Output (into ./output):
    verification_<ts>.json   full machine results incl. basis citations
    verification_latest.json
    verification_report.md    human-readable scorecard appended-ready for the vault
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
TIMEOUT = 60
RESULT_TIMEOUT = 300
MAX_RETRIES = 4

# ---------------------------------------------------------------------------
# The claims to verify — the load-bearing statistics in the briefing. Each maps
# to a citation [^n] in build-vs-buy-ria-ai-2026.md. `original_source` records
# what the article currently attributes the figure to, so the report can show
# attribution drift.
# ---------------------------------------------------------------------------
CLAIMS: list[dict] = [
    {"id": "c2_63pct", "footnote": "2,9",
     "claim": "63% of independent RIAs now use AI in some capacity, more than double the rate since 2023, per a 2026 Schwab Advisor Services study of 533 advisors.",
     "original_source": "Schwab Advisor Services / Logica Research (533 RIAs, Oct 2025)"},
    {"id": "c2_1in10", "footnote": "2,9",
     "claim": "Only about one in ten RIAs using AI have fully integrated it into their core business strategy (per the 2026 Schwab study).",
     "original_source": "Schwab Advisor Services"},
    {"id": "c3_cambridge", "footnote": "3",
     "claim": "81% of financial-services firms are adopting AI at some level and 40% are at advanced ('Scaling' or 'Transforming') maturity, per the Cambridge Judge Business School 2026 Global AI in Financial Services Report.",
     "original_source": "Cambridge Judge Business School (CCAF), May 2026"},
    {"id": "c3_agentic", "footnote": "3",
     "claim": "Agentic AI is already in active adoption among 52% of financial-services industry respondents (Cambridge Judge 2026 report).",
     "original_source": "Cambridge Judge Business School (CCAF)"},
    {"id": "c1_fed", "footnote": "1",
     "claim": "Work-related generative-AI adoption reached about 41% of the U.S. workforce as of November 2025, per a Federal Reserve FEDS Note.",
     "original_source": "Federal Reserve FEDS Notes"},
    {"id": "c21_hours", "footnote": "21,22",
     "claim": "AI advisor copilots Jump and Zocks report saving advisors 10+ hours per week; Equitable Advisors pilot participants reported saving 10+ hours/week in heavy client periods.",
     "original_source": "InvestmentNews / Zocks (vendor + trade press)"},
    {"id": "c27_funding", "footnote": "21,27",
     "claim": "Zocks raised a $45M Series B in January 2026 (co-led by Lightspeed and QED), bringing lifetime funding to $65M, and is used by more than 5,000 financial firms.",
     "original_source": "InvestmentNews"},
    {"id": "c24_merrill", "footnote": "24",
     "claim": "Merrill and Bank of America Private Bank launched an AI meeting solution they say can save advisors up to four hours per meeting across millions of meetings annually.",
     "original_source": "Bank of America newsroom"},
    {"id": "c34_cost", "footnote": "34",
     "claim": "Building custom wealth-management software costs roughly $40K-$600K+ up front and takes 12-36 months, versus $50K-$500K and 3-6 months to deploy an off-the-shelf platform, with custom maintenance running 15-20% of dev cost annually.",
     "original_source": "Appinventiv (vendor/dev-shop blog)"},
    {"id": "c32_overrun", "footnote": "32",
     "claim": "About 70% of software projects exceed their initial budgets, by an average of 27%.",
     "original_source": "The Wealth Mosaic / Docupace (citing Acquaint Softtech)"},
    {"id": "c60_multiples", "footnote": "60",
     "claim": "RIA EV/EBITDA multiples run roughly 8-11x for firms under $500M AUM, 10-15x for $500M-$3B, high-teens for $3B-$20B, and low-20s+ for $20B+; industry average ~10x.",
     "original_source": "Family Wealth Report (Advisor Growth Strategies & DeVoe)"},
    {"id": "c57_organic", "footnote": "54,57",
     "claim": "A firm growing ~12% organically could command an EBITDA multiple more than double that of a firm with no organic growth, and organic growth has surpassed M&A as the top priority for most advisory firms (per Cerulli, cited by Mercer Capital).",
     "original_source": "Mercer Capital (citing Cerulli)"},
]

OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["supported", "partially_supported", "unsupported", "contradicted"],
                "description": "How well current web evidence supports the claim as stated.",
            },
            "verified_figure": {
                "type": "string",
                "description": "The figure/fact the evidence actually supports, stated precisely. Empty string if none found.",
            },
            "primary_source": {
                "type": "string",
                "description": "URL of the most authoritative source found (prefer the original publisher/regulator over aggregators).",
            },
            "source_type": {
                "type": "string",
                "enum": ["primary", "trade_press", "vendor", "unknown"],
                "description": "Nature of the most authoritative source: primary (regulator/issuer/original study), trade_press, vendor (self-interested), or unknown.",
            },
            "notes": {
                "type": "string",
                "description": "One sentence explaining the verdict, noting any discrepancy, date, or caveat.",
            },
        },
        "required": ["verdict", "verified_figure", "primary_source", "source_type", "notes"],
        "additionalProperties": False,
    },
}

PROMPT_TEMPLATE = (
    "You are a financial-research fact-checker. Verify the following claim using "
    "current web research. Prefer the ORIGINAL primary source (regulator filing, "
    "the issuing company's own release, or the original study) over secondary "
    "aggregators or vendor marketing. Be strict: if the figure is close but not "
    "exact, or the attribution is wrong, mark it partially_supported and give the "
    "corrected figure. If a vendor is the only source for a self-interested metric "
    "(e.g. 'hours saved'), set source_type=vendor and reflect that in notes.\n\n"
    "CLAIM TO VERIFY:\n{claim}\n\n"
    "Currently attributed in the article to: {original_source}"
)


def _redacted(key: str) -> str:
    return "<missing>" if not key else f"set (len={len(key)}, ****{key[-2:]})"


def create_run(prompt: str, processor: str, api_key: str) -> str:
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
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
        time.sleep(delay)
        delay *= 2
    raise SystemExit("create_run failed after retries")


def get_result(run_id: str, api_key: str) -> dict:
    headers = {"x-api-key": api_key}
    url = f"{RUNS_URL}/{run_id}/result"
    # The result endpoint blocks until complete; one long call, with a couple of
    # retries in case the connection is dropped.
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
        time.sleep(delay)
        delay *= 2
    raise SystemExit("get_result failed after retries")


VERDICT_BADGE = {
    "supported": "✅ Supported",
    "partially_supported": "🟡 Partially",
    "unsupported": "⚠️ Unsupported",
    "contradicted": "❌ Contradicted",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 3 claim verification via Parallel Task API")
    ap.add_argument("--processor", default="base", help="lite|base|core|pro (depth vs. speed)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()

    key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[verify] PARALLEL_API_KEY: {_redacted(key)}  processor={args.processor}  claims={len(CLAIMS)}")
    if args.dry_run:
        for c in CLAIMS:
            print(f"  - {c['id']} [^{c['footnote']}]: {c['claim'][:90]}...")
        return
    if not key:
        raise SystemExit("PARALLEL_API_KEY not set. Aborting.")

    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []

    # Fan out: create all runs first, then collect — overlaps the research latency.
    pending = []
    for c in CLAIMS:
        prompt = PROMPT_TEMPLATE.format(claim=c["claim"], original_source=c["original_source"])
        run_id = create_run(prompt, args.processor, key)
        print(f"[verify] queued {c['id']} -> {run_id}")
        pending.append((c, run_id))
        time.sleep(0.5)

    for c, run_id in pending:
        print(f"[verify] collecting {c['id']} ...")
        res = get_result(run_id, key)
        out = res.get("output", {})
        content = out.get("content", {}) if isinstance(out, dict) else {}
        basis = out.get("basis", []) if isinstance(out, dict) else []
        results.append({
            "id": c["id"],
            "footnote": c["footnote"],
            "claim": c["claim"],
            "original_source": c["original_source"],
            "run_id": run_id,
            "status": res.get("run", {}).get("status"),
            "verdict": content.get("verdict"),
            "verified_figure": content.get("verified_figure"),
            "primary_source": content.get("primary_source"),
            "source_type": content.get("source_type"),
            "notes": content.get("notes"),
            "basis": basis,
        })

    # Persist machine output
    payload = {"generated_utc": ts, "processor": args.processor, "results": results}
    for name in (f"verification_{ts}.json", "verification_latest.json"):
        with open(os.path.join(args.outdir, name), "w") as f:
            json.dump(payload, f, indent=2)

    # Human-readable report
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    lines = [
        "---",
        "title: \"Verification Report — Build vs. Buy RIA AI Briefing\"",
        "type: Verification",
        f"date: {ts[:4]}-{ts[4:6]}-{ts[6:8]}",
        f"engine: \"Parallel.ai Task API (processor={args.processor})\"",
        "tags: [wealth-ai, fact-check, verification]",
        "---",
        "",
        "# Verification Report — Build vs. Buy RIA AI Briefing",
        "",
        "> [!info] Method",
        f"> Each load-bearing statistic was independently re-researched via the Parallel.ai Task API "
        f"(processor `{args.processor}`), which returns a structured verdict plus citations. "
        "Verdicts reflect what current web evidence supports, preferring primary sources over "
        "aggregators and flagging self-interested vendor metrics. Generated "
        f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} (UTC).",
        "",
        "## Scorecard",
        "",
        "| Verdict | Count |",
        "|---|---|",
    ]
    for v in ["supported", "partially_supported", "unsupported", "contradicted"]:
        if counts.get(v):
            lines.append(f"| {VERDICT_BADGE[v]} | {counts[v]} |")
    lines += ["", "## Claim-by-claim", ""]
    for r in results:
        badge = VERDICT_BADGE.get(r["verdict"], f"? {r['verdict']}")
        lines += [
            f"### {badge} — `[^{r['footnote']}]` {r['id']}",
            "",
            f"**Claim:** {r['claim']}",
            "",
            f"- **Originally attributed to:** {r['original_source']}",
            f"- **Verified figure:** {r['verified_figure'] or '—'}",
            f"- **Most authoritative source found:** {r['primary_source'] or '—'} "
            f"_({r['source_type'] or 'unknown'})_",
            f"- **Notes:** {r['notes'] or '—'}",
        ]
        # surface up to 3 citation URLs from the basis
        urls = []
        for b in r["basis"]:
            for cit in b.get("citations", []):
                u = cit.get("url")
                if u and u not in urls:
                    urls.append(u)
        if urls:
            lines.append(f"- **Task API citations:** " + ", ".join(f"<{u}>" for u in urls[:3]))
        lines.append("")
    lines += [
        "---",
        "> [!warning] Disclosure",
        "> This verification was produced by an AI research workflow (Parallel.ai Task API) "
        "with human review. Verdicts are research aids, not guarantees; confirm any figure "
        "against the linked primary source before relying on it. Vendor-reported metrics remain "
        "self-interested even when 'supported' (i.e. the vendor did publish the claim).",
    ]
    report_path = os.path.join(args.outdir, "verification_report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    print(f"[verify] DONE. verdicts={counts}")
    print(f"   json   : {os.path.join(args.outdir, 'verification_latest.json')}")
    print(f"   report : {report_path}")


if __name__ == "__main__":
    main()
