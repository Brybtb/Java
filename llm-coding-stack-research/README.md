# LLM Coding Stack Research

Research + recommendation for accessing coding LLMs at high volume
(~1B tokens/month, ~92% cache-hit, ~100 req/day) at the best quality/quota balance.

Separate, self-contained project (not related to the wealth-ai-workflow).

## Files
| File | Purpose |
|------|---------|
| `research_engine.py` | Parallel.ai Search API driver — 8 objectives, cited corpus |
| `output/REPORT.md` | Findings, plan-accuracy scorecard, cost model, recommendation |
| `output/SETUP.md` | Copy-paste / automatable Claude Code setup for the recommended hybrid |
| `output/corpus_latest.json` | Full structured research results |
| `output/sources_latest.json` | Deduped citation registry |
| `output/*_supplement.json`, `output/kimi_moderato.json` | Targeted follow-up searches |

## Run
```bash
export PARALLEL_API_KEY=...      # env only; never commit
python3 research_engine.py       # or --dry-run to preview the plan
```

## TL;DR recommendation
Hybrid: **MiniMax Token Plan Plus ($20, ~1.7B M3 tokens)** as workhorse +
**DeepSeek direct** (cache-hit ~$0.07/M, ideal for 92%-cache) for overflow +
**OpenCode Go ($10)** for model breadth, all driving Claude Code via
Anthropic-compatible endpoints (optionally behind LiteLLM / claude-code-router).
Two plan items corrected: MiMo "11B credits" ≠ tokens; Kimi "Moderato" is a chat
membership, not a coding token plan (use Kimi Code). See REPORT.md.

> Informational only; prices/quotas/model ids change monthly — verify live at setup.
