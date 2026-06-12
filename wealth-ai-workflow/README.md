# Wealth AI — Build vs. Buy Research → Substack Workflow

An end-to-end, reproducible workflow that researches the **"build vs. buy" AI decision
for RIAs** using the **Parallel.ai Search API**, then assembles a fully-cited,
Obsidian-ready Substack briefing with Chart.js + Excalidraw visuals.

## Pipeline

```
research_engine.py     build_assets.py        verify_claims.py        (synthesis: human + AI)
   │ Parallel.ai          │ Chart.js/Excalidraw  │ Parallel.ai Task API    │
   │ Search API           │                      │ (fact-check)            │
   ▼                      ▼                      ▼                         ▼
corpus_*.json          charts.html            verification_*.json      build-vs-buy-ria-ai-2026.md
sources_*.json         build-vs-buy.excalidraw verification_report.md   (the briefing)
```

1. **`research_engine.py`** — fires 6 structured objectives (adoption, build-side,
   buy-side, economics, governance, valuation) at the Parallel.ai **Search** API.
   Dedupes every result into a numbered **source registry** so each claim in the
   article is traceable to a URL + title + publish date + excerpt.
2. **`build_assets.py`** — emits framework-agnostic visuals: a standalone
   `charts.html` (Chart.js via CDN) and an importable `build-vs-buy.excalidraw`
   decision-flow scene.
3. **`verify_claims.py`** — Stage 3 fact-check. Runs the ~12 load-bearing
   statistics through the Parallel.ai **Task** API, which returns a structured
   verdict (`supported` / `partially_supported` / `unsupported` / `contradicted`)
   plus a `basis` of citations, reasoning, and confidence per claim. Writes a
   machine JSON + a human `verification_report.md` scorecard. Verified run:
   **9 supported, 1 partial, 2 unsupported** — corrections were folded back into
   the briefing and its disclosures.
4. **Synthesis** — `output/build-vs-buy-ria-ai-2026.md`: the Obsidian-flavored
   briefing. Citations `[^n]` map to `sources_latest.json`.

## Run it

```bash
export PARALLEL_API_KEY=sk-...     # env only — never commit this
python3 research_engine.py         # Stage 1: ~6 Search calls; writes corpus + sources
python3 build_assets.py            # Stage 2: writes charts.html + .excalidraw
python3 verify_claims.py           # Stage 3: ~12 Task API fact-checks; writes verification_report.md
python3 verify_claims.py --processor core   # deeper (slower) verification
python3 research_engine.py --dry-run        # preview a plan, no API calls
```

> **Security:** the key is read **only** from `PARALLEL_API_KEY`. It is never
> written to disk, logged, or committed. If a key was ever pasted into a chat,
> rotate it.

## Output to Obsidian

This repo can't reach a local Obsidian vault (it runs in an ephemeral cloud
container). To publish:

1. Copy `output/build-vs-buy-ria-ai-2026.md` into your vault, e.g.
   `Wealth AI/Briefings/`.
2. Copy `output/build-vs-buy.excalidraw` alongside it (open with the
   **Excalidraw** community plugin).
3. The ` ```chartjs ` blocks render with the **Obsidian Charts** plugin; the
   ` ```mermaid ` block renders natively. No plugins? Open `charts.html` in any
   browser for the same figures.

## Substack

Paste the markdown body into the Substack editor (it strips the frontmatter).
Chart.js/Mermaid don't run inside Substack — export each figure from
`charts.html` / Excalidraw as **PNG** and insert as images. Keep the
**Disclosures** section intact.

## Files

| File | Purpose |
|------|---------|
| `research_engine.py` | Stage 1 — Parallel.ai Search API research driver |
| `build_assets.py` | Stage 2 — Chart.js + Excalidraw asset generator |
| `verify_claims.py` | Stage 3 — Parallel.ai Task API claim verification |
| `output/corpus_*.json` | Full structured research results per objective |
| `output/sources_*.json` | Deduped, numbered citation registry (60 sources) |
| `output/verification_*.json` | Machine fact-check results (verdict + basis citations) |
| `output/verification_report.md` | Human-readable verification scorecard |
| `output/build-vs-buy-ria-ai-2026.md` | The Obsidian-ready briefing |
| `output/charts.html` | Standalone Chart.js figures |
| `output/build-vs-buy.excalidraw` | Importable decision-flow diagram |

## Disclosures

The briefing is informational only — not investment, legal, tax, or compliance
advice; no endorsements. Third-party figures (incl. vendor "hours saved" claims)
are reproduced from cited sources and not independently verified. See the full
disclosures block at the foot of the briefing.
