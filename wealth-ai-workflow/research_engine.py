#!/usr/bin/env python3
"""
Wealth AI — Build vs. Buy Research Engine
==========================================
A reusable research workflow that drives the Parallel.ai Search API to gather
cited, source-linked evidence on the "build vs. buy" decision RIAs face with AI.

Design goals
------------
* Reproducible: every run writes a timestamped JSON corpus + a flat source registry.
* Citeable: each finding keeps url + title + publish_date + excerpt so the
  downstream article can cite primary sources, not the model's memory.
* Safe: the API key is read ONLY from the PARALLEL_API_KEY environment variable.
  It is never written to disk, logged, or committed.

Usage
-----
    export PARALLEL_API_KEY=sk-...          # your key, env only
    python3 research_engine.py              # runs the full research plan
    python3 research_engine.py --dry-run    # prints the plan, makes no API calls

Output
------
    output/corpus_<timestamp>.json   # full structured results, per objective
    output/sources_<timestamp>.json  # deduped, numbered source registry
    output/corpus_latest.json        # symlink-style copy of the most recent run
    output/sources_latest.json
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

# ---------------------------------------------------------------------------
# The research plan. Each objective becomes one Search API call. The queries
# are intentionally diverse (Parallel recommends 2-3 angles per objective) so
# the engine surfaces primary sources rather than one echo chamber.
# ---------------------------------------------------------------------------
RESEARCH_PLAN: list[dict] = [
    {
        "id": "adoption_baseline",
        "topic": "RIA AI adoption baseline & pace",
        "objective": (
            "Find the most recent (2025-2026) statistics on how many RIA and "
            "financial advisory firms are adopting AI, what share have formal AI "
            "policies, and how mature that adoption is. Prefer Schwab, Orion, "
            "Kitces, and named industry surveys with specific percentages."
        ),
        "search_queries": [
            "Schwab RIA AI adoption study 2026 percentage formal policy",
            "financial advisor AI adoption survey statistics 2026 formal gen AI policy",
            "RIA AI adoption maturity most firms early stage 2026",
        ],
    },
    {
        "id": "build_side",
        "topic": "The build case — proprietary AI as a moat & recruiting magnet",
        "objective": (
            "Find evidence that some RIAs are BUILDING proprietary AI technology "
            "in-house and using it as a recruiting and growth advantage. Look for "
            "funding rounds, AUM growth, headcount growth, and quantified "
            "efficiency gains (e.g. percent of back-office time saved)."
        ),
        "search_queries": [
            "RIA building proprietary AI platform recruiting advantage advisors 2026",
            "tech-driven RIA in-house AI copilot cut back office time advisors growth",
            "wealth management firm build instead of buy AI software engineers 2026",
        ],
    },
    {
        "id": "buy_side",
        "topic": "The buy case — vendor copilots, time saved, enterprise deals",
        "objective": (
            "Find evidence on the BUY side: third-party AI copilots/notetakers for "
            "advisors (e.g. Jump, Zocks and peers), how much time they save, their "
            "funding, and enterprise/RIA adoption deals. Include quantified hours "
            "saved and number of firms onboarded."
        ),
        "search_queries": [
            "AI notetaker copilot financial advisors hours saved per week 2026",
            "Jump Zocks advisor AI funding enterprise RIA adoption agreement",
            "agentic operating system advisor tech stack vendor wealthtech 2026",
        ],
    },
    {
        "id": "economics",
        "topic": "Build vs. buy economics & cost framework",
        "objective": (
            "Find cost and tradeoff data for building custom wealth-management "
            "software in-house versus buying a platform: development cost ranges, "
            "implementation fees, the AUM threshold where building starts to pay "
            "off, and operational tradeoffs (speed, control, compliance burden)."
        ),
        "search_queries": [
            "custom wealth management software development cost range RIA 2026",
            "RIA platform implementation fee cost buy vs build threshold AUM",
            "build vs buy wealth management software tradeoffs control speed compliance",
        ],
    },
    {
        "id": "governance",
        "topic": "Compliance, SEC scrutiny & AI governance risk",
        "objective": (
            "Find what the SEC and compliance experts are saying about RIA use of "
            "AI in 2025-2026: examiner focus on AI governance, the marketing rule "
            "and AI-washing, vendor/third-party data risk, Reg S-P deadlines, and "
            "the human-review documentation expectation. Prefer SEC, Kitces, and "
            "named compliance sources."
        ),
        "search_queries": [
            "SEC examiners RIA AI governance documentation human review 2026",
            "SEC marketing rule AI washing over-hyping advisor compliance 2026",
            "RIA third party AI vendor client data risk Reg S-P deadline 2026",
        ],
    },
    {
        "id": "valuation",
        "topic": "Valuation, M&A & the strategic stakes",
        "objective": (
            "Find 2026 data on RIA valuations and M&A: EBITDA multiples by firm "
            "size, why organic growth and differentiation (not just scale) now "
            "drive multiples, and how technology/operating-model capability factors "
            "into enterprise value. Prefer Mercer Capital and named deal trackers."
        ),
        "search_queries": [
            "RIA M&A valuation multiples EBITDA 2026 by AUM size",
            "RIA organic growth differentiator valuation premium 2026 scale not enough",
            "RIA enterprise value technology operating model capability 2026",
        ],
    },
]


def _redacted(key: str) -> str:
    """Return a safe fingerprint of the key for logging — never the key itself."""
    if not key:
        return "<missing>"
    return f"set (len={len(key)}, ****{key[-2:]})"


def run_search(objective: str, search_queries: list[str], api_key: str) -> dict:
    """Execute one Search API call with retry + exponential backoff."""
    payload = {"objective": objective, "search_queries": search_queries}
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    delay = 2
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            # 429/5xx are retryable; 4xx (auth/validation) are not.
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                raise SystemExit(
                    f"Non-retryable API error HTTP {resp.status_code}: {resp.text[:300]}"
                )
        except requests.RequestException as e:
            last_err = f"network error: {e}"
        print(f"   retry {attempt}/{MAX_RETRIES} after {delay}s ({last_err})", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise SystemExit(f"Search failed after {MAX_RETRIES} attempts: {last_err}")


def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Wealth AI build-vs-buy research engine")
    parser.add_argument("--dry-run", action="store_true", help="print plan, no API calls")
    parser.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = parser.parse_args()

    api_key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[research_engine] PARALLEL_API_KEY: {_redacted(api_key)}")
    print(f"[research_engine] objectives: {len(RESEARCH_PLAN)}")

    if args.dry_run:
        for obj in RESEARCH_PLAN:
            print(f"  - {obj['id']}: {obj['topic']}")
            for q in obj["search_queries"]:
                print(f"        q: {q}")
        return

    if not api_key:
        raise SystemExit("PARALLEL_API_KEY not set in environment. Aborting.")

    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    corpus: list[dict] = []
    # Deduped source registry keyed by URL -> assigned citation number.
    source_index: dict[str, int] = {}
    sources: list[dict] = []

    for obj in RESEARCH_PLAN:
        print(f"[research_engine] running: {obj['id']} — {obj['topic']}")
        data = run_search(obj["objective"], obj["search_queries"], api_key)
        results = data.get("results", [])
        print(f"   -> {len(results)} results")
        norm_results = []
        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            if url not in source_index:
                num = len(sources) + 1
                source_index[url] = num
                sources.append(
                    {
                        "n": num,
                        "url": url,
                        "title": r.get("title", ""),
                        "domain": domain_of(url),
                        "publish_date": r.get("publish_date"),
                        "first_seen_topic": obj["topic"],
                    }
                )
            norm_results.append(
                {
                    "citation": source_index[url],
                    "url": url,
                    "title": r.get("title", ""),
                    "publish_date": r.get("publish_date"),
                    "excerpts": r.get("excerpts", []),
                }
            )
        corpus.append(
            {
                "id": obj["id"],
                "topic": obj["topic"],
                "objective": obj["objective"],
                "search_id": data.get("search_id"),
                "results": norm_results,
            }
        )
        time.sleep(1)  # be polite between calls

    corpus_path = os.path.join(args.outdir, f"corpus_{ts}.json")
    sources_path = os.path.join(args.outdir, f"sources_{ts}.json")
    with open(corpus_path, "w") as f:
        json.dump({"generated_utc": ts, "corpus": corpus}, f, indent=2)
    with open(sources_path, "w") as f:
        json.dump({"generated_utc": ts, "sources": sources}, f, indent=2)
    # latest copies for the synthesis step
    with open(os.path.join(args.outdir, "corpus_latest.json"), "w") as f:
        json.dump({"generated_utc": ts, "corpus": corpus}, f, indent=2)
    with open(os.path.join(args.outdir, "sources_latest.json"), "w") as f:
        json.dump({"generated_utc": ts, "sources": sources}, f, indent=2)

    print(f"[research_engine] DONE. {len(sources)} unique sources across {len(corpus)} topics.")
    print(f"   corpus : {corpus_path}")
    print(f"   sources: {sources_path}")


if __name__ == "__main__":
    main()
