#!/usr/bin/env python3
"""
FinLink — Daily RIA M&A Intelligence: Deep Research Engine (Parallel.ai)
=======================================================================
Two-layer research for the last-7-days RIA M&A intelligence brief:
  Layer A (Search API):  cited breadth — recent deals, AI moves, leaders/laggards.
  Layer B (Task API):    deep analytical synthesis with structured output + basis
                         citations (leaders vs laggards; cost-effective AI strategy
                         for 10-yr leadership).

Auth: x-api-key from PARALLEL_API_KEY (verified contract).
Run:  export PARALLEL_API_KEY=...; python3 deep_research.py [--dry-run] [--days 7]
Output: output/corpus_latest.json, sources_latest.json, analysis_latest.json
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.parse
from datetime import datetime, timezone, timedelta
import requests

SEARCH_URL = "https://api.parallel.ai/v1/search"
RUNS_URL   = "https://api.parallel.ai/v1/tasks/runs"
T, RT, RETRIES = 120, 360, 4

def red(k): return "<missing>" if not k else f"set(len={len(k)},****{k[-2:]})"
def dom(u):
    try: return urllib.parse.urlparse(u).netloc.replace("www.","")
    except Exception: return ""

# --- Layer A: Search objectives (last 7 days RIA M&A + AI) --------------------
def build_search_plan(window: str):
    return [
        {"id":"deals","topic":"RIA M&A deals — last 7 days",
         "objective":f"Find the most important RIA (registered investment adviser) and wealth-management M&A deals, acquisitions, mergers, and minority investments announced in the {window}. For each: acquirer, target, AUM, deal value/structure if disclosed, and the strategic rationale. Prefer Citywire RIA, RIABiz, WealthManagement.com, InvestmentNews, Financial Planning, Devoe, Echelon.",
         "queries":[f"RIA acquisition announced {window} AUM wealth management deal",
                    f"RIA M&A this week {window} acquires wealth firm",
                    "RIABiz Citywire RIA acquisition June 2026 AUM deal announced"]},
        {"id":"overlooked","topic":"Overlooked / under-covered RIA deals & moves — last 7 days",
         "objective":f"Find RIA M&A and wealth-management strategic moves from the {window} that are important but UNDER-covered: smaller sub-$1B deals, minority stakes, tech/AI tuck-ins, talent lift-outs, custodian/platform moves, or PE recapitalizations that got little mainstream coverage but signal strategy.",
         "queries":[f"small RIA deal minority stake tuck-in {window} wealth tech",
                    f"RIA lift-out team breakaway PE recapitalization {window}",
                    "under the radar wealth management acquisition June 2026 AI tuck-in"]},
        {"id":"ai_diff","topic":"How AI differentiates RIAs in 2026",
         "objective":f"Find concrete 2026 evidence of how AI differentiates RIA firms competitively: proprietary platforms, agentic workflows, productivity/AUM-per-advisor gains, organic-growth lift, and recruiting advantage. Recent ({window}) and 2026 broadly.",
         "queries":["RIA AI competitive differentiation 2026 proprietary platform organic growth",
                    "AI advisor productivity AUM per advisor recruiting advantage 2026",
                    "wealth management AI moat differentiation leaders 2026"]},
        {"id":"leaders","topic":"AI leaders among RIAs / wealth platforms",
         "objective":f"Find which RIA firms, aggregators, and wealth platforms are considered LEADERS in AI adoption in 2026 — named firms with specific AI initiatives, builds, partnerships, or results. Include any {window} announcements.",
         "queries":["leading RIA firms AI adoption 2026 named wealth management leaders",
                    "wealth platform AI initiative announcement 2026 advisor",
                    "RIA aggregator proprietary AI build 2026 leader"]},
        {"id":"laggards","topic":"AI laggards / risks among RIAs",
         "objective":"Find 2026 evidence of which kinds of RIA firms are LAGGING in AI (small firms, no formal policy, legacy tech stacks), the risks they face, adoption-gap statistics, and why incumbents fall behind.",
         "queries":["RIA AI laggards adoption gap small firms no policy 2026 risk",
                    "wealth management firms behind on AI legacy tech 2026",
                    "RIA AI adoption statistics gap integration 2026 most firms early"]},
        {"id":"strategy_cost","topic":"Cost-effective AI strategies for RIAs",
         "objective":"Find 2026 analysis of the most cost-effective AI strategies for RIAs aiming to be long-term leaders: build vs buy vs hybrid, hiring engineers, agentic operating systems, vendor copilots (Jump/Zocks etc.), data foundations, governance. Include costs and ROI where available.",
         "queries":["cost effective AI strategy RIA build vs buy 2026 ROI advisor",
                    "RIA AI operating model data foundation governance investment 2026",
                    "wealth firm AI roadmap long term leadership cost 2026"]},
    ]

# --- Layer B: Task API deep-analysis questions -------------------------------
ANALYSIS_SCHEMA = {
    "type":"json",
    "json_schema":{
        "type":"object",
        "properties":{
            "summary":{"type":"string","description":"2-4 sentence analytical answer."},
            "leaders":{"type":"array","items":{"type":"string"},
                       "description":"Named firms/categories identified as leaders, each with a one-line why. Empty if N/A."},
            "laggards":{"type":"array","items":{"type":"string"},
                        "description":"Named firms/categories identified as laggards, each with a one-line why. Empty if N/A."},
            "most_cost_effective":{"type":"array","items":{"type":"string"},
                       "description":"Ranked cost-effective AI strategies for 10-yr leadership, each with rationale/cost signal. Empty if N/A."},
            "confidence":{"type":"string","enum":["high","medium","low"]},
        },
        "required":["summary","leaders","laggards","most_cost_effective","confidence"],
        "additionalProperties":False,
    },
}
def build_analysis_questions(window: str):
    return [
        {"id":"leaders_laggards",
         "input":f"Based on current web research, which specific RIA firms, aggregators, and wealth platforms are the clearest LEADERS vs LAGGARDS in using AI as a competitive differentiator in 2026? Name firms where possible and explain why. Consider events from the {window}. Be objective; do not promote any single firm."},
        {"id":"cost_effective",
         "input":"Based on current web research and 2026 economics, what are the MOST COST-EFFECTIVE AI strategies for an RIA that wants to be an industry leader in 10 years? Rank them, and for each give the rough cost/ROI signal and why it compounds. Cover build vs buy vs hybrid, data foundations, agentic operating systems, governance, and talent."},
    ]

def search(obj, queries, key):
    h={"x-api-key":key,"Content-Type":"application/json"}; d=2
    for a in range(1,RETRIES+1):
        try:
            r=requests.post(SEARCH_URL,headers=h,json={"objective":obj,"search_queries":queries},timeout=T)
            if r.status_code==200: return r.json()
            if r.status_code not in (429,500,502,503,504): raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e: print(f"   search retry {a} ({e})",file=sys.stderr)
        time.sleep(d); d*=2
    raise SystemExit("search failed")

def task_create(prompt, processor, key):
    h={"x-api-key":key,"Content-Type":"application/json"}
    body={"input":prompt,"processor":processor,"task_spec":{"output_schema":ANALYSIS_SCHEMA}}; d=2
    for a in range(1,RETRIES+1):
        try:
            r=requests.post(RUNS_URL,headers=h,json=body,timeout=T)
            if r.status_code in (200,202): return r.json()["run_id"]
            if r.status_code not in (429,500,502,503,504): raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e: print(f"   task create retry {a} ({e})",file=sys.stderr)
        time.sleep(d); d*=2
    raise SystemExit("task create failed")

def task_result(run_id, key):
    h={"x-api-key":key}; url=f"{RUNS_URL}/{run_id}/result"; d=3
    for a in range(1,RETRIES+1):
        try:
            r=requests.get(url,headers=h,timeout=RT)
            if r.status_code==200: return r.json()
            if r.status_code not in (429,500,502,503,504): raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e: print(f"   task result retry {a} ({e})",file=sys.stderr)
        time.sleep(d); d*=2
    raise SystemExit("task result failed")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--days",type=int,default=7)
    ap.add_argument("--processor",default="core")
    ap.add_argument("--outdir",default=os.path.join(os.path.dirname(__file__),"output"))
    args=ap.parse_args()
    key=os.environ.get("PARALLEL_API_KEY","")
    today=datetime.now(timezone.utc).date()
    start=today-timedelta(days=args.days)
    window=f"last {args.days} days ({start.isoformat()} to {today.isoformat()})"
    plan=build_search_plan(window); qs=build_analysis_questions(window)
    print(f"[finlink] PARALLEL_API_KEY: {red(key)}  window={window}  search={len(plan)} analysis={len(qs)}")
    if args.dry_run:
        for o in plan: print("  search:",o["id"],"-",o["topic"])
        for q in qs: print("  task:",q["id"])
        return
    if not key: raise SystemExit("PARALLEL_API_KEY not set.")
    os.makedirs(args.outdir,exist_ok=True)
    ts=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Layer A
    corpus, idx, sources = [], {}, []
    for o in plan:
        print(f"[search] {o['id']} — {o['topic']}")
        data=search(o["objective"],o["queries"],key); res=data.get("results",[])
        print(f"   -> {len(res)} results")
        norm=[]
        for r in res:
            u=r.get("url","");
            if not u: continue
            if u not in idx:
                idx[u]=len(sources)+1
                sources.append({"n":idx[u],"url":u,"title":r.get("title",""),"domain":dom(u),
                                "publish_date":r.get("publish_date"),"first_seen_topic":o["topic"]})
            norm.append({"citation":idx[u],"url":u,"title":r.get("title",""),
                         "publish_date":r.get("publish_date"),"excerpts":r.get("excerpts",[])})
        corpus.append({"id":o["id"],"topic":o["topic"],"objective":o["objective"],
                       "search_id":data.get("search_id"),"results":norm})
        time.sleep(1)

    # Layer B
    print(f"[task] creating {len(qs)} deep-analysis runs (processor={args.processor})")
    pend=[(q, task_create(q["input"],args.processor,key)) for q in qs]
    for q,rid in pend: print(f"   queued {q['id']} -> {rid}")
    analysis=[]
    for q,rid in pend:
        print(f"[task] collecting {q['id']}")
        rj=task_result(rid,key); out=rj.get("output",{}) or {}
        analysis.append({"id":q["id"],"run_id":rid,"status":rj.get("run",{}).get("status"),
                         "content":out.get("content",{}),"basis":out.get("basis",[])})

    for nm,payload in [(f"corpus_{ts}.json",{"generated_utc":ts,"window":window,"corpus":corpus}),
                       ("corpus_latest.json",{"generated_utc":ts,"window":window,"corpus":corpus}),
                       (f"sources_{ts}.json",{"generated_utc":ts,"sources":sources}),
                       ("sources_latest.json",{"generated_utc":ts,"sources":sources}),
                       (f"analysis_{ts}.json",{"generated_utc":ts,"window":window,"analysis":analysis}),
                       ("analysis_latest.json",{"generated_utc":ts,"window":window,"analysis":analysis})]:
        with open(os.path.join(args.outdir,nm),"w") as f: json.dump(payload,f,indent=2)
    print(f"[finlink] DONE. {len(sources)} sources, {len(corpus)} search topics, {len(analysis)} analyses.")

if __name__=="__main__":
    main()
