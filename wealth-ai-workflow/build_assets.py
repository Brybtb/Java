#!/usr/bin/env python3
"""
Build portable visual assets for the Wealth AI build-vs-buy briefing.

Outputs (into ./output):
  * charts.html              — standalone Chart.js page (renders in any browser)
  * build-vs-buy.excalidraw  — importable Excalidraw scene (decision flow)

These are intentionally framework-agnostic so they work whether or not the
Obsidian vault has the Charts / Excalidraw community plugins installed. The
article markdown also embeds ```chartjs and ```mermaid fenced blocks for users
who DO have those plugins.

Run:
    python3 build_assets.py
"""
from __future__ import annotations
import json
import os

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# 1) Chart.js — standalone HTML with the three figures from the article.
#    Data is hard-coded from cited sources (see article Sources list).
# ---------------------------------------------------------------------------
CHARTS_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Wealth AI — Build vs. Buy: Charts</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#0f172a}
  h1{font-size:1.4rem} h2{font-size:1.05rem;margin-top:2.5rem;color:#1e293b}
  .card{border:1px solid #e2e8f0;border-radius:12px;padding:1rem 1.25rem;margin:1rem 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}
  small{color:#64748b}
  .note{background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:.6rem .9rem;font-size:.85rem}
</style>
</head>
<body>
<h1>Build vs. Buy — RIAs &amp; AI · Figures</h1>
<p class="note"><strong>Disclosure:</strong> All figures reproduced from cited third-party sources and not independently verified. Vendor "hours saved" claims are self-reported. Valuation ranges are illustrative market commentary, not appraisals. As of 2026-06-02.</p>

<div class="card">
  <h2>Fig 1 — The adoption gap (2025–26)</h2>
  <canvas id="c1" height="220"></canvas>
  <small>Sources: Schwab/Logica; Cambridge Judge Business School.</small>
</div>

<div class="card">
  <h2>Fig 2 — Vendor-reported time savings (self-reported)</h2>
  <canvas id="c2" height="220"></canvas>
  <small>FinMate (1–2 hrs/day quoted ≈7.5/wk); Zocks/Jump (10+/wk); Merrill–BofA (up to 4 hrs/meeting); DataDasher (15+/wk).</small>
</div>

<div class="card">
  <h2>Fig 3 — RIA EV/EBITDA multiples by scale</h2>
  <canvas id="c3" height="220"></canvas>
  <small>Source: Family Wealth Report / Advisor Growth Strategies &amp; DeVoe ranges; PE/scale context from Etna 2026 trends. Illustrative, not an appraisal.</small>
</div>

<script>
const blue="#2563eb",lblue="#93c5fd",violet="#7c3aed",lviolet="#c4b5fd",sky="#0ea5e9";
new Chart(c1,{type:"bar",data:{labels:["RIAs using AI","AI in core strategy","FS adopting AI","FS advanced maturity","Agentic AI active"],
 datasets:[{label:"% of firms",data:[63,10,81,40,52],backgroundColor:[blue,lblue,violet,lviolet,sky]}]},
 options:{plugins:{legend:{display:false},title:{display:true,text:"Everyone has AI; almost no one has integrated it"}},
 scales:{y:{beginAtZero:true,max:100,title:{display:true,text:"% of firms"}}}}});

new Chart(c2,{type:"bar",data:{labels:["FinMate AI","Zocks / Jump","Merrill–BofA (per meeting)","DataDasher"],
 datasets:[{label:"Hours saved / advisor / week",data:[7.5,10,4,15],backgroundColor:["#64748b",blue,"#f59e0b","#16a34a"]}]},
 options:{indexAxis:"y",plugins:{legend:{display:false},title:{display:true,text:"Vendor-reported time savings"}},
 scales:{x:{beginAtZero:true,title:{display:true,text:"Hours / week (Merrill figure is per-meeting)"}}}}});

new Chart(c3,{type:"bar",data:{labels:["< $500M AUM","$500M–$3B","$3B–$20B","> $20B / PE meta-RIA"],
 datasets:[{label:"EV/EBITDA (low)",data:[8,10,16,20],backgroundColor:"#1d4ed8"},
           {label:"EV/EBITDA (high)",data:[11,15,19,24],backgroundColor:"#60a5fa"}]},
 options:{plugins:{title:{display:true,text:"Multiples climb with scale — and scale needs a tech operating model"}},
 scales:{y:{beginAtZero:true,title:{display:true,text:"EV / EBITDA (x)"}}}}});
</script>
</body>
</html>
"""

with open(os.path.join(OUT, "charts.html"), "w") as f:
    f.write(CHARTS_HTML)


# ---------------------------------------------------------------------------
# 2) Excalidraw — decision flow scene. Minimal hand-authored .excalidraw JSON
#    (schema v2). Rectangles + bound arrows + text. Importable into Obsidian
#    Excalidraw plugin or excalidraw.com.
# ---------------------------------------------------------------------------

def rect(eid, x, y, w, h, bg, label_id):
    return {
        "id": eid, "type": "rectangle", "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": bg,
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": {"type": 3}, "seed": abs(hash(eid)) % 9_999_999,
        "version": 1, "versionNonce": abs(hash(eid + "n")) % 9_999_999,
        "isDeleted": False, "boundElements": [{"type": "text", "id": label_id}],
        "updated": 1, "link": None, "locked": False,
    }


def text(tid, x, y, w, h, txt, container):
    return {
        "id": tid, "type": "text", "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": None, "seed": abs(hash(tid)) % 9_999_999,
        "version": 1, "versionNonce": abs(hash(tid + "n")) % 9_999_999,
        "isDeleted": False, "boundElements": [], "updated": 1, "link": None,
        "locked": False, "fontSize": 16, "fontFamily": 1, "text": txt,
        "textAlign": "center", "verticalAlign": "middle", "containerId": container,
        "originalText": txt, "lineHeight": 1.25,
    }


def arrow(aid, x, y, points, start_id, end_id, label=None):
    el = {
        "id": aid, "type": "arrow", "x": x, "y": y,
        "width": abs(points[-1][0]), "height": abs(points[-1][1]),
        "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": {"type": 2}, "seed": abs(hash(aid)) % 9_999_999,
        "version": 1, "versionNonce": abs(hash(aid + "n")) % 9_999_999,
        "isDeleted": False, "boundElements": [], "updated": 1, "link": None,
        "locked": False, "points": points, "lastCommittedPoint": None,
        "startBinding": {"elementId": start_id, "focus": 0, "gap": 4} if start_id else None,
        "endBinding": {"elementId": end_id, "focus": 0, "gap": 4} if end_id else None,
        "startArrowhead": None, "endArrowhead": "arrow",
    }
    return el


elements = []

# Node layout (x, y, w, h, color, text)
nodes = [
    ("q1", 360, 40, 320, 80, "#a5d8ff", "Is this capability CORE to how\nwe differentiate & grow?"),
    ("buy1", 60, 200, 280, 90, "#b2f2bb", "BUY\nCommodity copilots, notetakers,\nmeeting intelligence"),
    ("q2", 380, 200, 300, 90, "#ffec99", "Does it touch client data,\nregulator visibility, or\nproprietary modeling?"),
    ("buy2", 740, 200, 260, 90, "#b2f2bb", "BUY / lightly configure\nSpeed beats control here"),
    ("q3", 360, 360, 340, 100, "#ffec99", "Do we have / can we hire\n1–2 engineers + an\nAI governance owner?"),
    ("buy3", 40, 380, 280, 90, "#ffc9c9", "BUY now, revisit in 12 mo\nDon't ship a black box\nyou can't supervise"),
    ("build", 740, 360, 300, 110, "#d0bfff", "BUILD the differentiating layer\nCOMPOSABLE HYBRID:\nbuy inference · build the moat"),
    ("gov", 340, 540, 380, 90, "#ffd8a8", "EVERY PATH ENDS HERE:\nGovernance + disclosure\nare non-negotiable"),
]
for nid, x, y, w, h, bg, txt in nodes:
    tid = nid + "_t"
    elements.append(rect(nid, x, y, w, h, bg, tid))
    elements.append(text(tid, x + 10, y + h / 2 - 20, w - 20, 40, txt, nid))

# Arrows (id, startNode, endNode, approximate points relative to start)
elements.append(arrow("a1", 420, 120, [[0, 0], [-180, 80]], "q1", "buy1"))      # core? No -> Buy1
elements.append(arrow("a2", 530, 120, [[0, 0], [0, 80]], "q1", "q2"))           # core? Yes -> q2
elements.append(arrow("a3", 680, 245, [[0, 0], [60, 0]], "q2", "buy2"))         # touch? No -> Buy2
elements.append(arrow("a4", 530, 290, [[0, 0], [0, 70]], "q2", "q3"))           # touch? Yes -> q3
elements.append(arrow("a5", 360, 410, [[0, 0], [-150, 0]], "q3", "buy3"))       # capacity? No -> Buy3
elements.append(arrow("a6", 700, 410, [[0, 0], [40, 0]], "q3", "build"))        # capacity? Yes -> Build
elements.append(arrow("a7", 200, 470, [[0, 0], [180, 70]], "buy3", "gov"))
elements.append(arrow("a8", 530, 460, [[0, 0], [0, 80]], "q3", "gov"))
elements.append(arrow("a9", 880, 470, [[0, 0], [-250, 70]], "build", "gov"))

# Title text (free-floating)
elements.append({
    "id": "title", "type": "text", "x": 360, "y": 0, "width": 360, "height": 28,
    "angle": 0, "strokeColor": "#1971c2", "backgroundColor": "transparent",
    "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1,
    "opacity": 100, "groupIds": [], "frameId": None, "roundness": None,
    "seed": 12345, "version": 1, "versionNonce": 54321, "isDeleted": False,
    "boundElements": [], "updated": 1, "link": None, "locked": False,
    "fontSize": 20, "fontFamily": 1,
    "text": "RIA AI: Build vs. Buy Decision Flow",
    "textAlign": "center", "verticalAlign": "top", "containerId": None,
    "originalText": "RIA AI: Build vs. Buy Decision Flow", "lineHeight": 1.25,
})

scene = {
    "type": "excalidraw",
    "version": 2,
    "source": "wealth-ai-workflow",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}

with open(os.path.join(OUT, "build-vs-buy.excalidraw"), "w") as f:
    json.dump(scene, f, indent=2)

print("Wrote:")
print("  output/charts.html")
print("  output/build-vs-buy.excalidraw")
