#!/usr/bin/env python3
"""
Financial Planning Agent — Rule Sourcing Engine (Parallel.ai Search API)
=======================================================================
The knowledge plane that *feeds* the deterministic engine. Mirrors the proven
pattern in ../../wealth-ai-workflow/research_engine.py: each objective is one
Search API call, results are deduped into a numbered source registry, and output
is written timestamped + _latest.

Here each objective is one DISCIPLINE in the "syndicate" — CFP, CFA, tax/estate/
state attorney, insurance, banking/lending, mortgage, enrolled agent/CPA, Social
Security/Medicare, student-loan, behavioral-finance — so every FOO rule can cite
primary, discipline-appropriate sources rather than the model's memory.

The deduped sources output is shaped to drop straight into
  ../foo_agent/rules/data/citations/sources.json

Usage:
    export PARALLEL_API_KEY=sk-...
    python3 source_rules.py --dry-run
    python3 source_rules.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

API_URL = "https://api.parallel.ai/v1/search"
TIMEOUT = 120
MAX_RETRIES = 4

# One objective per syndicate discipline. Queries favor PRIMARY sources
# (IRS/SSA/CFPB/DOL/statute) over secondary commentary.
RESEARCH_PLAN: list[dict] = [
    {
        "id": "cfp_foo",
        "discipline": "CFP",
        "topic": "Financial Order of Operations / cash-flow prioritization",
        "objective": (
            "Find authoritative guidance on the recommended order for allocating "
            "cash flow: starter emergency fund, capturing the full employer match, "
            "paying high-interest debt, full 3-6 month reserve, HSA, IRA, employer "
            "plan max, then taxable. Prefer CFP Board, Bogleheads, r/personalfinance "
            "flowchart, Money Guy FOO, and helloplaybook framing."
        ),
        "search_queries": [
            "financial order of operations emergency fund employer match high interest debt sequence",
            "personal finance flowchart prioritize savings 401k match Roth HSA taxable",
            "CFP Board cash flow planning emergency fund 3 to 6 months guidance",
        ],
    },
    {
        "id": "cfa_invest",
        "discipline": "CFA",
        "topic": "Asset allocation, withdrawal rates, capital market assumptions",
        "objective": (
            "Find evidence-based guidance on safe withdrawal rates (4% rule and "
            "critiques), sequence-of-returns risk, Guyton-Klinger guardrails, and "
            "long-horizon capital market assumptions used in Monte Carlo planning."
        ),
        "search_queries": [
            "safe withdrawal rate 4 percent rule sequence of returns risk research",
            "Guyton Klinger guardrails dynamic withdrawal strategy",
            "capital market assumptions expected return volatility retirement Monte Carlo",
        ],
    },
    {
        "id": "tax_attorney",
        "discipline": "tax_attorney",
        "topic": "Federal contribution limits, phase-outs, brackets, RMDs",
        "objective": (
            "Find the CURRENT IRS figures: 401(k)/403(b) elective deferral limit and "
            "catch-up, IRA limit and catch-up, HSA self/family limits and catch-up, "
            "Roth IRA MAGI phase-outs by filing status, standard deduction, ordinary "
            "income brackets, and RMD age. Prefer irs.gov primary pages."
        ),
        "search_queries": [
            "IRS 401k contribution limit catch up current year site:irs.gov",
            "IRS Roth IRA MAGI phase out limits filing status current year",
            "IRS HSA contribution limits self only family catch up current year",
        ],
    },
    {
        "id": "estate_attorney",
        "discipline": "estate_attorney",
        "topic": "Estate planning essentials & federal estate/gift exemption",
        "objective": (
            "Find authoritative guidance on core estate documents (will, durable POA, "
            "healthcare directive, beneficiary designations), the federal estate/gift "
            "tax exemption and annual gift exclusion, and step-up in basis. Prefer "
            "irs.gov, uniform law sources, and reputable estate bar materials."
        ),
        "search_queries": [
            "federal estate gift tax exemption annual exclusion current year IRS",
            "essential estate planning documents will power of attorney healthcare directive",
            "step up in basis inherited assets community property rules",
        ],
    },
    {
        "id": "state_attorney",
        "discipline": "state_attorney",
        "topic": "State income tax, homestead, community property",
        "objective": (
            "Find authoritative, state-by-state facts on: which states have no income "
            "tax, community-property states, and homestead exemption protections — the "
            "inputs to the engine's jurisdiction overlays."
        ),
        "search_queries": [
            "states with no income tax list current",
            "community property states list",
            "homestead exemption by state bankruptcy protection",
        ],
    },
    {
        "id": "insurance",
        "discipline": "insurance",
        "topic": "Life, disability, and umbrella coverage adequacy",
        "objective": (
            "Find guidance on right-sizing term life insurance (income-multiple and "
            "needs-analysis methods), long-term disability replacement ratios, and when "
            "umbrella liability is warranted."
        ),
        "search_queries": [
            "how much term life insurance income multiple needs analysis",
            "long term disability insurance income replacement percentage guidance",
            "umbrella liability insurance when needed net worth",
        ],
    },
    {
        "id": "banking_lending",
        "discipline": "banking_lending",
        "topic": "Emergency fund placement & high-yield savings",
        "objective": (
            "Find guidance on where to hold an emergency fund (HYSA, money market, "
            "T-bills), FDIC/NCUA insurance limits, and the high-interest debt threshold "
            "above which payoff beats investing."
        ),
        "search_queries": [
            "best place to keep emergency fund high yield savings money market FDIC",
            "FDIC insurance limit per depositor per bank",
            "high interest debt payoff vs invest threshold APR",
        ],
    },
    {
        "id": "mortgage",
        "discipline": "mortgage",
        "topic": "Mortgage payoff vs invest, refinance, PMI",
        "objective": (
            "Find guidance on prepaying a mortgage vs investing, when refinancing makes "
            "sense, removing PMI at 20% equity, and how mortgage rate vs expected return "
            "affects the decision."
        ),
        "search_queries": [
            "pay off mortgage early vs invest decision interest rate",
            "remove PMI 20 percent equity rules",
            "mortgage refinance break even analysis when worth it",
        ],
    },
    {
        "id": "enrolled_agent",
        "discipline": "enrolled_agent",
        "topic": "Roth conversions, bracket-filling, tax-efficient withdrawals",
        "objective": (
            "Find guidance on Roth conversion strategy, filling up to the top of a tax "
            "bracket, tax-efficient withdrawal sequencing in retirement, and the "
            "backdoor Roth for high earners."
        ),
        "search_queries": [
            "Roth conversion fill tax bracket strategy",
            "tax efficient withdrawal order retirement taxable tax deferred Roth",
            "backdoor Roth IRA high income strategy pro rata rule",
        ],
    },
    {
        "id": "social_security_medicare",
        "discipline": "social_security_medicare",
        "topic": "Claiming age, spousal benefits, IRMAA",
        "objective": (
            "Find SSA/CMS guidance on optimal Social Security claiming age, delayed "
            "retirement credits, spousal/survivor benefits, and Medicare IRMAA income "
            "thresholds that interact with Roth conversions."
        ),
        "search_queries": [
            "Social Security claiming age delayed retirement credits SSA",
            "Social Security spousal survivor benefit rules",
            "Medicare IRMAA income brackets current year",
        ],
    },
    {
        "id": "student_loan",
        "discipline": "student_loan",
        "topic": "Federal repayment plans, forgiveness, refinance trade-offs",
        "objective": (
            "Find Department of Education guidance on federal student-loan repayment "
            "plans (IDR/SAVE), PSLF, and the trade-offs of refinancing federal loans to "
            "private (loss of forgiveness/protections)."
        ),
        "search_queries": [
            "federal student loan income driven repayment plans current",
            "public service loan forgiveness PSLF eligibility",
            "refinance federal student loans private trade offs lose protections",
        ],
    },
    {
        "id": "behavioral_finance",
        "discipline": "behavioral_finance",
        "topic": "Adherence, automation, and behavioral guardrails",
        "objective": (
            "Find research on why automating savings, paying yourself first, and "
            "snowball-vs-avalanche psychology improve plan adherence — the behavioral "
            "case behind the deterministic ordering."
        ),
        "search_queries": [
            "automate savings pay yourself first adherence research",
            "debt snowball vs avalanche behavioral motivation study",
            "behavioral finance commitment devices financial goals",
        ],
    },
]


def _redacted(key: str) -> str:
    return "<missing>" if not key else f"set (len={len(key)}, ****{key[-2:]})"


def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def run_search(objective: str, search_queries: list[str], api_key: str) -> dict:
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"objective": objective, "search_queries": search_queries}
    delay, last_err = 2, None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                raise SystemExit(f"Non-retryable HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.RequestException as e:
            last_err = f"network error: {e}"
        print(f"   retry {attempt}/{MAX_RETRIES} after {delay}s ({last_err})", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise SystemExit(f"Search failed after {MAX_RETRIES} attempts: {last_err}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Syndicate rule-sourcing engine")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()

    api_key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[source_rules] PARALLEL_API_KEY: {_redacted(api_key)}")
    print(f"[source_rules] disciplines: {len(RESEARCH_PLAN)}")

    if args.dry_run:
        for o in RESEARCH_PLAN:
            print(f"  - {o['id']} ({o['discipline']}): {o['topic']}")
        return
    if not api_key:
        raise SystemExit("PARALLEL_API_KEY not set. Aborting.")

    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    corpus, source_index, sources = [], {}, []
    for obj in RESEARCH_PLAN:
        print(f"[source_rules] {obj['id']} — {obj['topic']}")
        data = run_search(obj["objective"], obj["search_queries"], api_key)
        results = data.get("results", [])
        print(f"   -> {len(results)} results")
        norm = []
        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            if url not in source_index:
                n = len(sources) + 1
                source_index[url] = n
                sources.append({
                    "n": n, "url": url, "title": r.get("title", ""),
                    "domain": domain_of(url), "publish_date": r.get("publish_date"),
                    "discipline": obj["discipline"], "source_type": "unknown",
                })
            norm.append({"citation": source_index[url], "url": url,
                         "title": r.get("title", ""), "excerpts": r.get("excerpts", [])})
        corpus.append({"id": obj["id"], "discipline": obj["discipline"],
                       "topic": obj["topic"], "objective": obj["objective"], "results": norm})
        time.sleep(1)

    for name, payload in [
        (f"corpus_{ts}.json", {"generated_utc": ts, "corpus": corpus}),
        ("corpus_latest.json", {"generated_utc": ts, "corpus": corpus}),
        (f"sources_{ts}.json", {"generated_utc": ts, "sources": sources}),
        ("sources_latest.json", {"generated_utc": ts, "sources": sources}),
    ]:
        with open(os.path.join(args.outdir, name), "w") as f:
            json.dump(payload, f, indent=2)

    print(f"[source_rules] DONE. {len(sources)} sources across {len(corpus)} disciplines.")
    print("   Review sources_latest.json, then merge into "
          "../foo_agent/rules/data/citations/sources.json")


if __name__ == "__main__":
    main()
