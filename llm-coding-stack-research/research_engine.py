#!/usr/bin/env python3
"""
LLM Coding Stack — Subscription/API Research Engine (Parallel.ai Search API)
===========================================================================
Researches the cost/quota/quality tradeoffs of the coding-LLM access options in
the user's plan, for a high-volume profile: ~1B tokens/month (~92% cache-hit),
~100 requests/day. Emits a cited, deduped corpus the synthesis step turns into a
recommendation + setup instructions.

Auth: x-api-key from PARALLEL_API_KEY env only (verified contract 2026-06).
Run:  export PARALLEL_API_KEY=...; python3 research_engine.py [--dry-run]
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.parse
from datetime import datetime, timezone
import requests

API_URL = "https://api.parallel.ai/v1/search"
TIMEOUT, MAX_RETRIES = 120, 4

RESEARCH_PLAN = [
    {"id": "openai_codex", "topic": "OpenAI ChatGPT Plus / Codex $20 plan — coding limits",
     "objective": "Find the current (2026) usage limits, rate limits, and model access for the OpenAI ChatGPT Plus $20/month plan and the Codex CLI / Codex coding agent. How many messages/requests, which models (GPT-5/Codex), weekly or 5-hour caps, and any token quotas. Is heavy coding agent use viable on Plus vs needing Pro/Business?",
     "queries": ["ChatGPT Plus $20 Codex usage limits 2026 weekly cap coding agent",
                 "OpenAI Codex CLI rate limits Plus vs Pro plan requests per day 2026",
                 "Codex coding agent message limits GPT-5 ChatGPT Plus quota"]},
    {"id": "minimax", "topic": "MiniMax coding plan (M2) token quota",
     "objective": "Find MiniMax's coding subscription / token plan details in 2026: the MiniMax M2 model, any '1.7 billion tokens per month' style plan, price, rate limits, Claude Code / coding-agent compatibility, and coding benchmark quality vs Claude/GPT.",
     "queries": ["MiniMax M2 coding plan token quota price 2026 Claude Code compatible",
                 "MiniMax M2 1.7 billion tokens per month subscription coding agent",
                 "MiniMax M2 coding benchmark SWE-bench quality vs Sonnet 2026"]},
    {"id": "mimo", "topic": "Xiaomi MiMo token/credit plan",
     "objective": "Find details on Xiaomi MiMo (MiMo-7B / MiMo coding model) and any token or '11 billion credits' subscription plan in 2026: what a 'credit' equals vs a token, price, access method (API/CLI), rate limits, and coding quality. Distinguish credits from tokens explicitly.",
     "queries": ["Xiaomi MiMo coding model credits plan price 2026 API access",
                 "MiMo 11 billion credits subscription tokens difference coding",
                 "Xiaomi MiMo coding benchmark quality API rate limits 2026"]},
    {"id": "kimi", "topic": "Kimi (Moonshot) K2 'Moderato' plan",
     "objective": "Find Moonshot Kimi coding subscription details in 2026, especially a plan tier called 'Moderato': price, token/request quota, the Kimi K2 model, Claude Code / Anthropic-compatible endpoint support, rate limits, and coding quality benchmarks.",
     "queries": ["Kimi K2 Moderato plan price token quota 2026 coding subscription",
                 "Moonshot Kimi coding plan Claude Code compatible Anthropic endpoint",
                 "Kimi K2 coding benchmark SWE-bench quality 2026"]},
    {"id": "opencode", "topic": "OpenCode (and OpenCode Zen / GO) $10 plan",
     "objective": "Find what 'OpenCode GO' or OpenCode Zen is in 2026: the open-source OpenCode coding agent and any $10/month plan or hosted model gateway. Price, models included, token/request limits, and how it routes to providers.",
     "queries": ["OpenCode Zen GO plan $10 month models included 2026 coding agent",
                 "OpenCode coding agent subscription pricing models gateway 2026",
                 "OpenCode Zen pricing token limits providers routing"]},
    {"id": "openrouter", "topic": "OpenRouter prepaid $20/month for coding",
     "objective": "Find how OpenRouter pricing/credits work in 2026 for a capped ~$20/month prepaid budget on coding models: per-token pricing of top coding models (DeepSeek, Qwen, GLM, Kimi, MiniMax), prompt caching support and discounts, BYOK, rate limits, and the free-tier vs paid behavior.",
     "queries": ["OpenRouter pricing 2026 prepaid credits coding models per token DeepSeek Qwen GLM",
                 "OpenRouter prompt caching discount supported models 2026",
                 "OpenRouter rate limits credits $20 budget coding Claude Code"]},
    {"id": "deepseek", "topic": "DeepSeek API direct — price & caching",
     "objective": "Find DeepSeek API pricing in 2026: per-million-token input/output cost for the latest DeepSeek (V3.x / coder), the context-caching / cache-hit discount (cache hit vs miss price), off-peak discounts, rate limits, and coding benchmark quality. Emphasize the cache-hit price since the user is ~92% cache-hit.",
     "queries": ["DeepSeek API pricing 2026 cache hit miss price per million tokens",
                 "DeepSeek V3 coder context caching discount off-peak pricing 2026",
                 "DeepSeek coding benchmark SWE-bench quality 2026 vs Claude"]},
    {"id": "caching_compat", "topic": "Prompt caching economics + Claude Code provider routing",
     "objective": "Find how prompt caching economics differ across providers in 2026 (Anthropic vs OpenAI vs DeepSeek vs OpenRouter vs Chinese labs) — cache write vs read pricing and discount sizes — and how to point coding agents like Claude Code at alternative Anthropic-compatible endpoints (ANTHROPIC_BASE_URL / proxies like LiteLLM, claude-code-router). Critical for a ~92% cache-hit workload.",
     "queries": ["prompt caching cache read price discount Anthropic OpenAI DeepSeek 2026 comparison",
                 "Claude Code ANTHROPIC_BASE_URL alternative model proxy LiteLLM router 2026",
                 "claude code router connect deepseek kimi glm minimax anthropic compatible endpoint"]},
]


def red(k): return "<missing>" if not k else f"set(len={len(k)},****{k[-2:]})"

def run_search(obj, queries, key):
    payload = {"objective": obj, "search_queries": queries}
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    d = 2
    for a in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
            if r.status_code == 200: return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            print(f"   retry {a} ({e})", file=sys.stderr)
        time.sleep(d); d *= 2
    raise SystemExit("search failed after retries")

def dom(u):
    try: return urllib.parse.urlparse(u).netloc.replace("www.", "")
    except Exception: return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()
    key = os.environ.get("PARALLEL_API_KEY", "")
    print(f"[engine] PARALLEL_API_KEY: {red(key)}  objectives={len(RESEARCH_PLAN)}")
    if args.dry_run:
        for o in RESEARCH_PLAN: print(f"  - {o['id']}: {o['topic']}")
        return
    if not key: raise SystemExit("PARALLEL_API_KEY not set.")
    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    corpus, idx, sources = [], {}, []
    for o in RESEARCH_PLAN:
        print(f"[engine] {o['id']} — {o['topic']}")
        data = run_search(o["objective"], o["queries"], key)
        res = data.get("results", [])
        print(f"   -> {len(res)} results")
        norm = []
        for r in res:
            u = r.get("url", "")
            if not u: continue
            if u not in idx:
                idx[u] = len(sources) + 1
                sources.append({"n": idx[u], "url": u, "title": r.get("title", ""),
                                "domain": dom(u), "publish_date": r.get("publish_date"),
                                "first_seen_topic": o["topic"]})
            norm.append({"citation": idx[u], "url": u, "title": r.get("title", ""),
                         "publish_date": r.get("publish_date"), "excerpts": r.get("excerpts", [])})
        corpus.append({"id": o["id"], "topic": o["topic"], "objective": o["objective"],
                       "search_id": data.get("search_id"), "results": norm})
        time.sleep(1)
    for nm, payload in [(f"corpus_{ts}.json", {"generated_utc": ts, "corpus": corpus}),
                        ("corpus_latest.json", {"generated_utc": ts, "corpus": corpus}),
                        (f"sources_{ts}.json", {"generated_utc": ts, "sources": sources}),
                        ("sources_latest.json", {"generated_utc": ts, "sources": sources})]:
        with open(os.path.join(args.outdir, nm), "w") as f: json.dump(payload, f, indent=2)
    print(f"[engine] DONE. {len(sources)} unique sources across {len(corpus)} topics.")

if __name__ == "__main__":
    main()
