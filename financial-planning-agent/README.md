# Financial Planning Agent (`foo-agent`)

A **deterministic, advisor-grade financial planning engine**. Same inputs → same
auditable output, every recommendation traceable to a rule and a cited source.
The decision logic is a codified **Financial Order of Operations** (FOO) —
inspired by helloplaybook.com and the Money Guy FOO — and an LLM is used (if at
all) only to *explain* the result, never to *decide* it.

Built to fold the best-of capabilities of the leading platforms into one
reproducible engine: cash-flow/retirement **projection** (eMoney/RightCapital),
**probability of success via seeded Monte Carlo** (MoneyGuidePro), **scenario /
what-if comparison** (MGP Play Zone / eMoney Decision Center), a citation-backed
**insights** generator (Holistiplan/Asset-Map), and a **white-labeled PDF**.

> ⚠️ **Decision-support only.** Output is not personalized advice; it must be
> reviewed and approved by a qualified fiduciary adviser. See *Compliance* below.

## Why deterministic

Two strictly separated planes:

| Plane | What it does | Properties |
|---|---|---|
| **Decision plane** (`foo_agent/`) | profile → recommendations + projection + probabilities | pure: no network, no wall-clock (`as_of` injected), randomness only via a **seeded** RNG, `Decimal` money math, total rule ordering, versioned + checksummed output |
| **Knowledge / validation plane** (`research/`) | sources and verifies the rules + assumptions | reuses this repo's Parallel.ai Search/Task pattern + legal MCP tools |

Monte Carlo stays deterministic by **pinning the seed + the Capital Market
Assumptions version + the trial count** — identical inputs always reproduce the
same probability of success and the same PDF.

## Install & test

```bash
pip install -e ".[dev]"     # numpy, pyyaml, jsonschema, jinja2, matplotlib, weasyprint
pytest                      # 46 tests: determinism, MC reproducibility, PDF repro, DSL safety
```

## CLI

```bash
export PYTHONPATH=.
P=tests/golden/profiles/young_saver_TX.json

foo-plan validate-ruleset                      # integrity-check the knowledge base
foo-plan plan       --profile $P               # FOO recommendations (+ audit trace)
foo-plan project    --profile $P               # deterministic multi-year projection
foo-plan montecarlo --profile $P --seed 42 --trials 10000
foo-plan scenario   --base $P --scenario examples/scenario_retire_at_67.json
foo-plan interview  --profile partial.json     # next guided-interview question
foo-plan explain    --profile $P               # plain-English narration (no LLM)
foo-plan report     --profile $P --brand examples/branding.example.yaml \
                    --pdf plan.pdf --md plan.md

# Phase 2 — dynamic workflow + optimizers
foo-plan workflow        --profile $P          # adaptive: next question OR selected modules + plan
foo-plan social-security --profile $P --pia 2800 --fra 67   # claiming-age optimizer
foo-plan roth            --profile $P           # Roth-conversion / bracket-fill
foo-plan withdraw        --profile $P           # tax-efficient withdrawal order
foo-plan assetmap        --profile $P --png map.png         # one-page household map

# Phase 3 — estate, risk, document intake, web UI
foo-plan estate          --profile $P          # estate-tax projection + GRAT/SLAT/ILIT modeling
foo-plan risk            --profile $P          # Risk Number + alignment + stress tests
foo-plan ingest --form1040 return.txt --profile $P   # parse a 1040 into profile fields
python3 web/app.py --port 8765                 # dynamic-workflow web UI (stdlib only)
```

### Web UI

`python3 web/app.py` serves a dependency-free single-page app (Python stdlib
`http.server`) with a **Copilot** chat tab and a **Guided form** tab. Both walk the
**dynamic workflow**: ask the next adaptive question, then render the selected
modules, plan, and a downloadable white-labeled PDF. The engine stays
deterministic; the web layer is pure I/O.

### AI Copilot (LLM mode)

The Planning Copilot has two modes (`foo_agent/agents/copilot.py`):
- **Deterministic** (default, zero dependencies): conversationalizes the adaptive
  interview, runs the orchestrator, and narrates the plan — fully reproducible.
- **LLM mode**: a bounded tool-calling loop over the **Tool/Contract plane**
  (`foo_agent/agents/engine_tools.py`). The model can only obtain facts by calling
  engine tools, and every reply passes the **guard** (`explain/guard.py`) — so the
  AI may phrase, but can never author a number that isn't in a tool Result.

Enable LLM mode with Gemini:
```bash
export GEMINI_API_KEY=...          # never committed; read from env only
export GEMINI_MODEL=gemini-3.5-flash   # optional; this is the default
python3 web/app.py                 # then tick "AI mode (Gemini)" in the Copilot tab
```
The adapter (`foo_agent/agents/llm.py`) calls Gemini `v1beta generateContent` with
the key in the `x-goog-api-key` header and `responseMimeType: application/json`. If
no key is present, the copilot silently stays in deterministic mode.

### Dynamic workflow (helloplaybook-style, deterministic)

`foo-plan workflow` adapts to the client instead of always running everything:

1. **Collecting** — if the profile is incomplete, it returns the *next* guided
   question and stops (driven by `interview/statemachine.py`).
2. **Ready** — once complete, it deterministically **selects which modules are
   relevant** (`workflow/orchestrator.py`, safe-DSL conditions over the profile +
   derived facts), runs the core plan plus those modules, and reports the reason
   each was included. A 34-year-old gets projection + Monte Carlo + Asset-Map; a
   63-year-old additionally gets Social Security, Roth-conversion, and withdrawal
   modules.

(`foo-plan` is the console script; equivalently `python cli/foo_plan.py …`.)

## Library

```python
import foo_agent
result = foo_agent.full_plan(profile, as_of="2026-06-14", seed=42, trials=10000)
# result: recommendations + projection + monte_carlo + insights + trace + disclosures
```

## How a rule works (rules-as-data)

Rules live in `foo_agent/rules/data/*.rules.yaml`. Each is declarative and
auditable; conditions use a **safe DSL** (no `eval`/`exec`):

```yaml
- id: foo.employer_match.capture_full
  order: 200
  condition: "accounts.employer_401k.match_offered == true and contributions.employer_401k.pct < accounts.employer_401k.match_pct_cap"
  action: { type: recommend_contribution, calculator: employer_match.capture_full }
  citations: [1, 8]          # required, non-empty; must exist in citations/sources.json
```

Dated dollar parameters (contribution limits, brackets, CMAs) live in
`rules/data/jurisdiction/` and `rules/data/assumptions/`, selected by `as_of`.
The loader **fails closed** on a missing citation, an out-of-band order, a
schema-version mismatch, or params that don't bracket the date.

## The syndicate (knowledge plane)

```bash
export PARALLEL_API_KEY=sk-...
python research/source_rules.py --dry-run        # one objective per discipline
python research/verify_rules.py --processor core # each rule = a verified claim
python research/syndicate.py                     # cross-validate FOO across lenses
python research/verify_assumptions.py --year 2026
python research/legal_validate.py                # legal-MCP question pack (ERISA/estate/homestead)
```

Disciplines: CFP, CFA, tax/estate/state attorney, insurance, banking/lending,
mortgage, enrolled agent/CPA, Social Security/Medicare, student-loan,
behavioral-finance. Attorney lenses validate against **primary law** via the
Descrybe and legal-research MCP tools.

> **Security:** every research script reads `PARALLEL_API_KEY` from the
> environment only — never logged, never committed.

## Compliance

`foo_agent/compliance/` stamps every Result with `requires_advisor_review: true`
and a disclosure block (`policy.yaml`); the report/PDF layer refuses to render
without them. Framing is SEC-marketing-rule aware: no performance guarantees,
assumptions disclosed, human-in-the-loop required.

## Status & roadmap

- **Phase 1 (done):** FOO engine, projection, seeded Monte Carlo, scenarios,
  insights, interview, white-labeled PDF, research/verification pipeline. TY2026
  federal parameters **verified** via the live Parallel.ai pipeline.
- **Phase 2 (done):** dynamic-workflow orchestrator (adaptive module selection),
  Roth-conversion/bracket-fill optimizer, tax-efficient withdrawal planner, Social
  Security claiming optimizer, Asset-Map visual household map. TX/CA state facts
  verified against statute.
- **Phase 3 (done):** estate-tax projection + wealth-transfer strategy modeling
  (GRAT/SLAT/ILIT, annual gifting), Risk Number + alignment + stress tests,
  document ingestion (deterministic 1040 parser + merge; OCR/AI fenced as the
  non-deterministic boundary), more states (FL/NY/WA + TX/CA), and a stdlib web
  UI — all wired into the dynamic orchestrator. TY2026 estate figures verified
  ($15M exemption, 40%, $19k annual exclusion; 12 estate + 5 inheritance states).
- **Beyond:** real OCR/LLM extraction adapters, full state tax-bracket coverage,
  estate-flow waterfall visualization, persistence/multi-client, auth.
