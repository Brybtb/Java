# CLAUDE.md — Financial Planning Agent

Read this first. When the user says **"continue"**, resume from **Current state →
Next** below.

## What this is
`foo-agent`: a **deterministic, advisor-grade financial planning engine** with an
**AI-native Planning Copilot** on top. The contract is **"AI proposes, the engine
computes, the advisor approves"** — an LLM may phrase output and choose which tools
to call, but every number comes from the deterministic engine and the guard
(`foo_agent/explain/guard.py`) rejects any figure the AI tries to invent.

Full critique + roadmap is in **`STRATEGY.md`** (the source of truth for direction).

## Current state (Phases 1–4 complete, merged to `master`)
- Engine: FOO rules, projection, seeded Monte Carlo, scenarios, insights, optimizers
  (estate, risk, Roth, Social Security, withdrawal), dynamic orchestrator, compliance,
  white-labeled PDF.
- Correctness (C1–C10): proper MAGI, RMDs, SS+taxes in projection, graduated/state
  estate (NY cliff), decumulation rules, risk capacity vs tolerance, fat-tail Monte
  Carlo, all 50 states + DC, joint-survivor longevity.
- AI wedge: Tool/Contract plane (`foo_agent/agents/engine_tools.py`), Planning Copilot
  (`foo_agent/agents/copilot.py`), generalized guard, chat web UI.
- **Live Gemini** wired (`foo_agent/agents/llm.py`, model `gemini-2.5-flash`).
- **Full test suite green** (`pytest`); kept green before every commit.

## Next (what "continue" should start)
**Phase 5 — platform foundation** (see STRATEGY.md §G): persistence + multi-client
data model (Supabase/Postgres: immutable `profile_version`/`plan_result`/`agent_run`/
`audit_log`), FastAPI replacing the stdlib `web/app.py`, auth + tenant scoping, an
append-only audit log. This is what lets the copilot remember clients between sessions
and makes it a real multi-firm product. Supabase MCP tools are available for migrations.

## How to run (macOS)
```
python3.12 -m venv .venv && source .venv/bin/activate   # 3.12: newer Pythons lack some wheels
python -m pip install -e .
python -m pytest                # must stay green (currently 85)
PYTHONPATH=. python web/app.py --port 8765   # open http://127.0.0.1:8765
```
PDF export needs `brew install pango`.

## Gemini / secrets
- `GEMINI_API_KEY` and `GEMINI_MODEL` are supplied via `.claude/settings.local.json`
  (gitignored — NOT committed). They reach Bash tool runs automatically.
- **Never print, echo, or commit the key.** If AI mode is needed and the key is
  missing, ask the user to add it to `.claude/settings.local.json`; the copilot falls
  back to deterministic mode without it.

## Working rules (non-negotiable)
- **Determinism:** no wall-clock in the decision path (inject `as_of`); `Decimal` money
  math; seeded Monte Carlo; versioned + checksummed output. Run `pytest` before every
  commit — determinism/golden tests must pass.
- **AI is fenced:** agents call only `engine_tools.call_tool`; all AI prose goes through
  `explain/guard.py`. Never let an LLM author a number that reaches output.
- **Citations:** every rule/insight needs a source in `rules/data/citations/sources.json`
  (loader fails closed otherwise).
- **Research:** use the **Parallel.ai** pipeline in `research/` (key in env), not ad-hoc web.
- **Git:** develop on branch `claude/financial-planning-agent-b5yxqp`; commit with clear
  messages; open a PR only when asked.

## Map
- Engine: `foo_agent/engine/`, `foo_agent/calculators/`, `foo_agent/rules/`
- Modeling: `foo_agent/projection/`, `foo_agent/montecarlo/`, `foo_agent/scenarios/`, `foo_agent/insights/`
- Optimizers: `foo_agent/optimize/`  ·  Agents: `foo_agent/agents/`
- Orchestrator: `foo_agent/workflow/`  ·  Interview: `foo_agent/interview/`
- Report: `foo_agent/report/`  ·  Ingestion: `foo_agent/ingest/`  ·  Compliance: `foo_agent/compliance/`
- CLI: `cli/foo_plan.py`  ·  Web: `web/`  ·  Research: `research/`  ·  Tests: `tests/`
