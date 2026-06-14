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
```

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

- **Phase 1 (this build):** FOO engine, projection, seeded Monte Carlo,
  scenarios, insights, interview, white-labeled PDF, research/verification
  pipeline. Parameters are seeded **placeholders** pending a live run of the
  verification scripts.
- **Phase 2:** Roth-conversion/bracket-fill + tax-efficient withdrawal optimizer,
  Social Security claiming, Asset-Map visual household map, more states.
- **Phase 3:** estate-tax projection + estate visualization + strategy modeling
  (GRAT/SLAT/ILIT), Risk Number + stress tests, document OCR (1040/estate/P&C),
  web UI.
