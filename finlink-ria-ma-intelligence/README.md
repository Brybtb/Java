# FinLink — Daily RIA M&A Intelligence

Fills the finlink daily RIA-M&A intelligence skeleton using Parallel.ai deep research,
focused on RIA M&A + how AI differentiates firms (leaders/laggards) + the most
cost-effective AI strategies to lead in 10 years. Separate, self-contained project.

## Files
| File | Purpose |
|------|---------|
| `deep_research.py` | Parallel.ai engine: Search (6 objectives) + Task/deep (2 analyses) |
| `output/finlink-daily-ma-intelligence-2026-06-13.md` | The filled, vault-ready brief |
| `output/corpus_latest.json` | Search results per objective |
| `output/sources_latest.json` | Deduped citation registry |
| `output/analysis_latest.json` | Task API deep analyses (leaders/laggards, cost strategy) |

## Run
```bash
export PARALLEL_API_KEY=...                 # env only; never commit
python3 deep_research.py --days 7 --processor core   # or --dry-run
```
Re-run daily; `--days N` sets the window. Output is timestamped + `_latest`.

> Informational only; third-party figures unverified; verify before acting.
