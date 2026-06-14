#!/usr/bin/env python3
"""
Generate an importable Excalidraw scene for the 10-Year RIA AI Leadership Sequence.
Hand-authored .excalidraw (schema v2): a rising 7-step staircase, color-coded by
phase, with a thesis banner. Output: output/ria-ai-10yr-sequence.excalidraw
Run: python3 build_excalidraw.py
"""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

# Excalidraw palette (bg, stroke) per phase
PHASE = {
    "found": ("#a5d8ff", "#1971c2"),  # blue   - foundation
    "quick": ("#99e9f2", "#0c8599"),  # cyan   - quick ROI
    "diff":  ("#d0bfff", "#6741d9"),  # violet - differentiation
    "scale": ("#b2f2bb", "#2f9e44"),  # green  - scale (last)
}

# step: (num, phase, title, sub, cost)
STEPS = [
    (1, "found", "Modern data foundation first",
     "Lakehouse / client-360. Everything rides on it.", "~$200K-$2M +$50K-$500K/yr - payback 12-36mo"),
    (2, "quick", "Buy vendor copilots / workflow automation",
     "Fastest time-to-value; 30-60% faster admin.", "SaaS $5K-$50K+/mo + $50K-$500K integration"),
    (3, "quick", "Advisor-assist AI (LLM copilots + RAG)",
     "RAG over your own docs; big advisor time savings.", "Pilot $25K-$250K - prod $100K-$1M+/yr - 6-24mo"),
    (4, "diff", "Hybrid: build ONLY the proprietary 'alpha' layer",
     "Buy the core; build tax-aware / private-mkts valuation.", "Build $500K-$5M+ - highest defensibility"),
    (5, "diff", "Early governance & model-risk controls",
     "Cheap insurance; enables safe scaling.", "$50K-$500K setup + $50K-$300K/yr"),
    (6, "scale", "Agentic OS - only after foundations",
     "Highest upside; worst ROI if sequenced too early.", "Pilot $100K-$1M+ - prod $1M-$10M+"),
    (7, "scale", "Lean talent + partnerships",
     "Talent compounds proprietary pipelines.", "ML eng ~$180K-$250K+ - team $600K-$1.8M/yr"),
]

elements = []

def seed(s): return abs(hash(s)) % 2_000_000_000

def rect(eid, x, y, w, h, bg, stroke, txtid):
    return {"id": eid, "type": "rectangle", "x": x, "y": y, "width": w, "height": h,
            "angle": 0, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": "solid",
            "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": {"type": 3}, "seed": seed(eid),
            "version": 1, "versionNonce": seed(eid + "n"), "isDeleted": False,
            "boundElements": [{"type": "text", "id": txtid}], "updated": 1, "link": None, "locked": False}

def textbound(tid, cid, x, y, w, h, txt, size=16, color="#1e1e1e"):
    return {"id": tid, "type": "text", "x": x, "y": y, "width": w, "height": h, "angle": 0,
            "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
            "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None, "seed": seed(tid),
            "version": 1, "versionNonce": seed(tid + "n"), "isDeleted": False, "boundElements": [],
            "updated": 1, "link": None, "locked": False, "fontSize": size, "fontFamily": 1,
            "text": txt, "textAlign": "left", "verticalAlign": "middle", "containerId": cid,
            "originalText": txt, "lineHeight": 1.25}

def freetext(tid, x, y, txt, size=16, color="#1e1e1e", w=600, align="left"):
    return {"id": tid, "type": "text", "x": x, "y": y, "width": w, "height": size * 1.5, "angle": 0,
            "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
            "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None, "seed": seed(tid),
            "version": 1, "versionNonce": seed(tid + "n"), "isDeleted": False, "boundElements": [],
            "updated": 1, "link": None, "locked": False, "fontSize": size, "fontFamily": 1,
            "text": txt, "textAlign": align, "verticalAlign": "top", "containerId": None,
            "originalText": txt, "lineHeight": 1.25}

def arrow(aid, sx, sy, ex, ey, color="#e8590c"):
    return {"id": aid, "type": "arrow", "x": sx, "y": sy, "width": abs(ex - sx), "height": abs(ey - sy),
            "angle": 0, "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
            "strokeWidth": 3, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
            "frameId": None, "roundness": {"type": 2}, "seed": seed(aid), "version": 1,
            "versionNonce": seed(aid + "n"), "isDeleted": False, "boundElements": [], "updated": 1,
            "link": None, "locked": False, "points": [[0, 0], [ex - sx, ey - sy]],
            "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
            "startArrowhead": None, "endArrowhead": "arrow"}

# Title + thesis banner
elements.append(freetext("title", 40, 20, "The 10-Year RIA AI Leadership Sequence", 28, "#1971c2", 900))
elements.append(freetext("subtitle", 40, 60, "Ranked by compounding ROI per dollar  -  most cost-effective path to lead in a decade", 16, "#495057", 900))
banner = rect("banner", 40, 96, 900, 50, "#ffec99", "#f08c00", "banner_t")
elements.append(banner)
elements.append(textbound("banner_t", "banner", 50, 108, 880, 28,
                          "SEQUENCE BEATS SPEND  -  proprietary foundation models aren't cost-justified except for the largest incumbents", 15, "#5c3c00"))

# Staircase: each step indents right + steps down, implying a rising stair (read top->bottom = 1->7)
BAR_W, BAR_H, GAP = 720, 96, 26
x0, y0, indent = 40, 176, 34
for i, (num, phase, title, sub, cost) in enumerate(STEPS):
    bg, stroke = PHASE[phase]
    x = x0 + i * indent
    y = y0 + i * (BAR_H + GAP)
    rid, tid = f"s{num}", f"s{num}_t"
    elements.append(rect(rid, x, y, BAR_W, BAR_H, bg, stroke, tid))
    # number badge (separate dark circle + text)
    elements.append({"id": f"b{num}", "type": "ellipse", "x": x + 14, "y": y + 30, "width": 38, "height": 38,
                     "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "#1e1e1e", "fillStyle": "solid",
                     "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
                     "frameId": None, "roundness": None, "seed": seed(f"b{num}"), "version": 1,
                     "versionNonce": seed(f"b{num}n"), "isDeleted": False,
                     "boundElements": [{"type": "text", "id": f"b{num}_t"}], "updated": 1, "link": None, "locked": False})
    elements.append(textbound(f"b{num}_t", f"b{num}", x + 14, y + 38, 38, 22, str(num), 20, "#ffffff"))
    # bound multi-line label inside the bar
    label = f"{title}\n{sub}\n{cost}"
    elements.append(textbound(tid, rid, x + 64, y + 14, BAR_W - 80, BAR_H - 24, label, 14, "#1e1e1e"))

# Compounding arrow up the right side
top_y = y0 + 6 * (BAR_H + GAP) + BAR_H // 2
bot_y = y0 + BAR_H // 2
ax = x0 + 6 * indent + BAR_W + 40
elements.append(arrow("compound", ax, top_y, ax, bot_y, "#f08c00"))
elements.append(freetext("compound_lbl", ax + 12, (top_y + bot_y) // 2, "COMPOUNDING ADVANTAGE", 13, "#f08c00", 260))

# Footer disclosure
fy = y0 + 7 * (BAR_H + GAP) + 10
elements.append(freetext("foot", 40, fy,
    "FinLink - RIA M&A Intelligence 2026-06-13 - Source: Parallel.ai deep research (Task API, medium confidence).\nInformational only; not advice; no endorsements. Cost ranges are directional 2026 estimates, unverified. Verify before acting.",
    12, "#868e96", 900))

scene = {"type": "excalidraw", "version": 2, "source": "finlink-ria-ma-intelligence",
         "elements": elements, "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"}, "files": {}}

path = os.path.join(OUT, "ria-ai-10yr-sequence.excalidraw")
with open(path, "w") as f:
    json.dump(scene, f, indent=2)
print("wrote", path, "with", len(elements), "elements")
