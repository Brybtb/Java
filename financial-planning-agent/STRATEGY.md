# Strategy & Critique: The First AI-Native, Agentic Financial Planning Platform

## Context

`foo-agent` (merged to `master`, Phases 1–3) is a **deterministic, advisor-grade**
planning engine: rules-as-data FOO + projection + seeded Monte Carlo + scenarios +
insights + optimizers (estate, risk, Roth, Social Security, withdrawal) + dynamic
orchestrator + compliance + white-labeled PDF + a stdlib web UI. Every output is
reproducible, versioned, checksummed, citation-backed, and gated for advisor review.

**Goal of this round (decided with the user):** produce a board-level, brutally
honest **critique + roadmap** — reviewed through veteran CFP/CFA/estate-attorney/
tax/retirement-income/Medicare-SS/insurance/lending expert lenses, grounded in the
live product — charting how this becomes the **first AI-native, agentic** planning
platform that out-classes RightCapital, MoneyGuidePro, eMoney, Holistiplan,
Nitrogen, Wealth.com, Luminary, and Vanilla.

**Decisions locked:** deliverable = this strategy doc (no code yet); agentic stance
= *deterministic core as trust moat + agent layers on top + agents propose
strategies as ideas (advisor-approved, never auto-applied)*; attack all four fronts
(**Planning, Tax, Estate, Risk**); research henceforth via **Parallel.ai** (not Exa).

**Method:** full code inventory + expert-lens critique + a live run of the product
(`http://127.0.0.1:8765`) on the HNW estate profile, which already exposed a real
gap (see B1).

---

## A. What's RIGHT — the moat to protect

1. **Determinism + auditability** — same inputs → byte-identical output; full
   per-rule trace; versioned + checksummed. No competitor can defend its numbers
   line-by-line; we can. This is the wedge, not a constraint.
2. **Citation-backed rules** — every rule/insight carries a source; loader fails
   closed on a missing citation. Primary-law/IRS verification pipeline exists.
3. **Compliance-first** — advisor-review gate + disclosures on every result;
   SEC-marketing-rule awareness baked in.
4. **Dynamic orchestration** — situation-aware module selection is genuinely novel
   and the seed of the "agentic" behavior.
5. **Safe, fenced AI boundary** — the `explain/guard.py` pattern (AI may narrate,
   never introduce a number/rule) is the template for all future AI.
6. **Clean, reusable architecture** — rules-as-data + calculator registry +
   declarative module/insight conditions make new capability cheap to add.

---

## B. Expert-panel critique, by product section
*(Each item: the expert lens → the finding. Verdict scale: ✅ solid · 🟡 partial · ❌ gap.)*

**B1. FOO recommendation engine** (`engine/`, `rules/data/foo_core.rules.yaml`)
🟡 CFP/behavioral: tuned for **accumulators**. Live proof: the $38M HNW retiree
returned only **2 recommendations** + a (nonsensical at that wealth) "backdoor Roth"
insight. ❌ No **decumulation** ruleset (drawdown order, RMDs, bracket management,
Roth-conversion windows, IRMAA tiers). ❌ Only a single retirement goal; no
education/home/major-purchase goals. 🟡 Protection step is a crude income-multiple.

**B2. Tax** (`calculators/tax.py`, `optimize/roth_conversion.py`, `ingest/`)
❌ Tax attorney/EA/CPA: **MAGI is proxied by gross income** (`contributions.py`) —
mis-routes Roth eligibility for high earners with deductions. ❌ No NIIT (3.8%),
IRMAA, AMT, capital-gains stacking/0%-bracket harvesting, QBI, SALT cap, state tax
in the conversion math. ❌ No **multi-year** tax projection / lifetime-tax
minimization (Holistiplan/RightCapital's core). 🟡 1040 parser is shallow (text
only; no real OCR, no Schedules, no K-1/1099).

**B3. Estate** (`optimize/estate.py`)
🟡 Estate attorney: **flat 40%** above exemption — ignores graduated rates, **prior
taxable gifts**, the **DSUE/portability election requirement**, and **state estate
tax dollar-modeling** (esp. the NY "cliff"). ❌ No basis step-up modeling, no
liquidity-to-pay-tax analysis. 🟡 Strategies are notional (no GRAT term/§7520 rate,
SLAT reciprocal-trust trap, QPRT, CRT/CLAT, ILIT Crummey mechanics, valuation
discounts). ❌ No estate-flow **waterfall visualization** (Vanilla/Wealth.com core).

**B4. Retirement income / projection / Monte Carlo** (`projection/`, `montecarlo/`)
🟡 Retirement-income specialist/CFA: projection is a **single mean-return path**;
MC uses **normal** returns (understates fat tails + sequence-of-returns risk;
bootstrap/regime models preferred). ❌ **Social Security, RMDs, and taxes are not in
the projection cash flow** → funded ratio & P(success) are biased. ❌ No healthcare/
LTC cost modeling, no dynamic spending/guardrails wired into MC, no pension/annuity,
no part-time income. 🟡 Spending replacement is a flat 80%.

**B5. Social Security** (`optimize/social_security.py`)
🟡 SS specialist: requires **PIA as input** (no estimation from earnings history or
the SSA statement). ❌ No spousal/survivor/divorced-spouse benefits, no taxation-of-
benefits, no IRMAA interaction, no integration into the household projection. 🟡
Longevity is a fixed input, not actuarial/joint-life.

**B6. Risk** (`optimize/risk.py`)
🟡 CFA/Nitrogen: Risk Number from **equity % only** (no factor/duration/credit/
concentration); when no questionnaire is given, tolerance is mapped from the same
allocation → **alignment is trivially "aligned"** (circular). ❌ No actual portfolio
holdings, no risk *capacity* vs *tolerance*, no proposal generation, no fee/tax drag,
no benchmark/percentile.

**B7. Insurance** (`calculators/protection.py`)
🟡 Insurance specialist: heuristic income-multiple only. ❌ No human-life-value vs
needs analysis, no DI own-occ nuance, no **LTC**, no umbrella sizing by net worth,
no policy review/1035, no survivor-income gap.

**B8. Banking / lending / mortgage** (`calculators/debt.py`)
🟡 Lending/mortgage specialist: avalanche only. ❌ No mortgage amortization, refi
break-even, recast, ARM-reset, HELOC, cash-out, DTI, or rate-vs-expected-return
decisioning; no credit/liquidity optimization.

**B9. Data model** (`schemas/profile.schema.json`)
❌ Single household (no spouse-level income/expense/age split in modeling); no
account **holdings/cost-basis** (blocks step-up, harvesting, location); no multiple
goals; no real-estate/business detail; no beneficiaries; no liability detail
(amortization); no monthly cash flow; no insurance policies; no equity comp/RSU/options.

**B10. Ingestion** (`ingest/`)
🟡 Holistiplan/FP Alpha: deterministic 1040 **text** parser only. ❌ No real OCR/PDF,
no estate-doc or P&C-declaration parsing, no brokerage-statement/CSV import, no
account aggregation.

**B11. Reporting / UX** (`report/`, `web/`)
✅ PDF is white-labeled + byte-reproducible. ❌ No client portal, no interactive
what-if UI, no document vault, no e-sign, no estate waterfall / Asset-Map
relationship lines; web UI is minimal and stateless.

**B12. Orchestration & explanation** (`workflow/`, `explain/`)
✅ Dynamic module selection + deterministic interview are differentiators. ❌ No
conversational NL copilot, no memory/persistence, no proactive monitoring, no
multi-goal sequencing, no runtime expert panel.

**B13. Compliance** (`compliance/`)
✅ Gate + disclosures. ❌ No persisted audit log, no Reg BI/Form CRS artifacts, no
archiving/e-delivery, no per-firm policy config, no PII handling/encryption.

---

## C. Bugs & correctness defects (concrete, fix-first)

1. **MAGI = gross-income proxy** (`calculators/contributions.py`) → wrong Roth
   routing. Fix: compute MAGI from income − above-the-line items.
2. **Insight semantics at extreme wealth** — "backdoor Roth" fired for a $38M
   client. Fix: net-worth/age guardrails on insights + decumulation insight set.
3. **HNW/decumulation rule gap** — sparse recommendations for retirees. Fix: add a
   decumulation rule band (RMD, drawdown order, bracket-fill, IRMAA).
4. **Estate tax model** — flat 40%, ignores prior gifts/DSUE/state. Fix: graduated
   unified-credit calc + state estate dollar-modeling (start with NY cliff).
5. **RMDs not modeled** (`optimize/withdrawal_plan.py`, projection) → understated
   retirement tax. Fix: add RMD schedule (age 73/75 per SECURE 2.0).
6. **SS/RMD/taxes absent from projection cash flow** → biased funded ratio &
   P(success). Fix: unify income sources + taxes into the projection engine.
7. **Risk alignment is circular** when no questionnaire. Fix: separate risk
   *capacity* (from plan) vs *tolerance* (from questionnaire); require questionnaire.
8. **MC return model** — normal, single-asset. Fix: bootstrap/Student-t + asset
   classes + correlation; keep the seed for reproducibility.
9. **State coverage** — 5 of 51 jurisdictions; NY/WA brackets are placeholders; WA
   cap-gains excise unmodeled. Fix: Parallel.ai-verified bracket fill, all states.
10. **No spousal modeling** — ages/benefits/longevity are single-person. Fix:
    household-level (joint life, survivor) modeling.

---

## D. Competitive gap matrix (what each incumbent has that we don't — yet)

- **RightCapital:** tax-bracket-aware multi-year distribution + Roth optimization,
  student-loan module, account aggregation, client portal, budgeting.
- **MoneyGuidePro:** goals-based "Play Zone," health-care/LTC cost engine, annuity
  modeling, Social Security maximization, client-driven what-if.
- **eMoney:** detailed monthly cash-flow planning, account aggregation, **client
  portal + document vault**, estate flowcharts, fact finder.
- **Holistiplan:** real 1040 **OCR** + scenario tax analysis + white-label tax
  letters + multi-year tax projections.
- **Nitrogen:** holdings-based Risk Number, proposal generation, portfolio
  analytics, stress testing, client risk questionnaire at scale.
- **Wealth.com / Vanilla / Luminary:** document drafting/analysis, **estate
  visualization/waterfall**, estate-tax projection, advanced strategy modeling
  (GRAT/SLAT/CLAT/QPRT) for HNW/UHNW.

**Our durable advantages vs all:** deterministic + cited + auditable; one engine
spanning all four fronts; agentic orchestration; explainability as compliance.

---

## E. The AI-Native / Agentic vision (deterministic core + agent mesh)

**Principle: "AI proposes, the engine computes, the advisor approves."** AI never
emits a number; it selects inputs, drafts narrative, and surfaces ideas — the
deterministic engine produces every figure, the `guard` enforces it, and nothing
becomes a plan of record without a logged advisor approval.

**The architectural bet (from the design agent):** the system has exactly **two
non-deterministic boundaries** — (a) *ingestion* (documents/feeds → profile) and
(b) *narration/orchestration* (Result → language or → a search request). The whole
agentic platform is built by **generalizing three seams that already exist**, behind
one new plane:

- **`explain/guard.py`** → the fence for all AI prose ("AI may phrase, never compute").
- **`scenarios/compare.py` + `optimize/*`** → the template for the strategy proposer
  (search over deterministic evaluations).
- **`ingest/extract.py`** → the pure-merge boundary for aggregation + document AI.

**Three planes:**
1. **Deterministic core** (today's `foo_agent`, unchanged behavior).
2. **Tool/Contract plane** (NEW, the only door): `foo_agent/agents/engine_tools.py`
   exposes each pure function (`plan/full_plan/project/montecarlo/scenario/roth/ss/
   withdraw/estate/risk/interview.next`) as a typed tool returning the Result + its
   determinism stamps (`engine_version/ruleset_checksum/input_hash/mc_seed`). Agents
   may call only these — no direct calculator imports, no arithmetic that reaches output.
3. **Agent mesh** (NEW, fenced, every action logged):
   - **Planning Copilot** — NL chat that turns utterances into tool calls; uses
     `interview/statemachine.py` to guarantee data completeness; replies pass the
     extended guard before reaching the user.
   - **Financial Experts Panel** — `research/syndicate.py` promoted to runtime
     (`agents/panel.py`): each persona reviews *this client's Result* and attaches
     cited critiques as data under `result["panel"]`, labeled advisory (never a number).
   - **Strategy Proposer** — `optimize/search.py` (pure generators + ranker) +
     `agents/proposer.py` (fenced LLM that only narrows a *bounded* grid and narrates
     the winner). Every candidate is a deterministic engine run; reproducible from
     `(base_profile, generator_version, grid_spec, ruleset_checksum, cma_version, seed)`.
   - **Autonomous ingestion** — aggregation (Plaid/Akoya) + document AI (1040/K-1/
     estate/P&C); fetch/extract is the fenced boundary, the *merge* stays pure with
     `{value, confidence, source_doc, page}` provenance + advisor confirm on low confidence.
   - **Proactive monitors** — KB-drift (re-verify params via the Parallel.ai pipeline →
     *proposed* diffs, never auto-applied), plan-drift (re-run + `compare`, triggers
     authored in the safe DSL), and deadlines (RMD/contribution/gift-year, pure).

**Determinism preserved:** an `agent_run` log records `{model_id, prompt_version,
tool-Result input_hashes, tool_calls, guard_verdict}` for every action — the `Trace`
philosophy lifted to the mesh, so any agent decision is replayable and provably
introduced no new figure. The `compliance/wrapper.py` gate extends to "a proposal
cannot become a plan of record without an approval event."

---

## F. Wishlist across ten orders of magnitude
*(Each tier ~10× the ambition/effort of the previous.)*

- **10⁰ — Correctness (days):** fix C1–C10; insight guardrails; decumulation rules.
- **10¹ — Depth (weeks):** SS+RMD+taxes inside projection; graduated/state estate;
  risk capacity vs tolerance; bootstrap MC; all-50-state params (Parallel.ai).
- **10² — Platform (weeks):** persistence + multi-client/household data model;
  FastAPI; auth; client portal; audit-log persistence.
- **10³ — Copilot (weeks):** NL Planning Copilot (tools over the engine); document
  AI ingestion; account aggregation (Plaid/custodian).
- **10⁴ — Agent mesh (months):** runtime multi-agent Financial Experts panel;
  agentic strategy proposer; proactive monitoring/alerts.
- **10⁵ — Domain completeness (months):** full tax engine (NIIT/AMT/IRMAA/QBI/cap-
  gains/state); estate engine (GRAT/CRT/QPRT/valuation/liquidity + waterfall);
  insurance needs engine; lending/mortgage engine; healthcare/LTC.
- **10⁶ — Ecosystem (quarters):** advisor+client co-planning, e-sign/vault,
  CRM/custodian/billing integrations, white-label SaaS.
- **10⁷ — Governance & scale (quarters):** SOC2, model-risk governance, open
  API/marketplace of verified rule packs, multi-tenant scale.
- **10⁸ — Always-on fiduciary (year):** continuous re-planning as data changes;
  tax-loss harvesting + direct indexing; held-away account guidance; AI compliance
  supervision with full audit trails.
- **10⁹–10¹⁰ — Category redefinition:** the trusted "operating system for financial
  advice" — every recommendation deterministic, cited, auditable, continuously
  expert-reviewed; regulatory-grade explainability; consumer + advisor + enterprise;
  multi-country. The thing that makes the incumbents legacy.

---

## G. Prioritized roadmap (Phase 4 → 9)

Two tracks run in parallel: a **Correctness track** (the C-list / B-list fixes —
days, highest trust impact, can ship immediately on today's engine) and the
**Platform/Agentic track** below (leads with the cheapest, highest-"wow" wedge).

- **Phase 4 — Tool Plane + Planning Copilot (the wedge).** NL intake + plan +
  what-if, every number provably from the engine. New: `agents/engine_tools.py`,
  `agents/copilot.py`, generalize `explain/guard.py` (percentages/ages, multi-Result
  allowed set, data-driven prefixes), `web/api.py` (FastAPI) `/v1/copilot/turn`.
  *Verify:* golden-conversation tests (fixed transcript → identical tool calls +
  Result hashes); guard rejects fabricated figures.
- **Phase 5 — Platform foundation.** Supabase schema (`firm/advisor/household/
  profile_version/plan_result/agent_run/proposal/document/audit_log` + RLS),
  `foo_agent/store/` repository (immutable, content-addressed by `input_hash`),
  auth + tenant scoping, `audit/log.py` (hash-chained). *Verify:* cross-tenant RLS
  blocked; stored `plan_result` re-hashes to its `input_hash`.
- **Phase 6 — Strategy Proposer (Tax + Estate).** `optimize/search.py` (pure
  generators: Roth ladder, gifting/SLAT/GRAT, glidepath, SS claiming + ranker) +
  `agents/proposer.py` (bounded grid narrowing + guarded narration); proposal
  lifecycle + Celery grid search. *Verify:* same grid → same ranking bytes;
  approval-gate test.
- **Phase 7 — Experts Panel + Autonomous Ingestion (all fronts).** `agents/panel.py`
  (runtime `syndicate.py`, citation-integrity-checked, advisory-labeled);
  `ingest/extract.py` extended (`merge_aggregation/estate_doc/pc_declaration/k1`) +
  `ingest/connectors/`. *Verify:* panel cached/reproducible by version tuple; merge
  purity; provenance on every ingested field.
- **Phase 8 — Proactive Monitoring + Risk depth.** `monitors/` (kb_drift → proposed
  param diffs; plan_drift via `compare` + DSL triggers; deadlines pure) on Celery
  beat. *Verify:* deterministic deadline tests across `as_of`; KB-drift never
  auto-applies (param checksum unchanged until approval).
- **Phase 9 — Compliance/SOC2 hardening + e-delivery.** PII field encryption,
  e-sign, consent versioning, guard-rejection telemetry, retention, AI-content
  marketing-rule disclosures. *Verify:* books-and-records retrieval (any client
  message → its prompt+Result+guard verdict); SOC2 control evidence.

---

## H. Platform, infra & compliance requirements

**Recommended stack (all Python-native, extends `pyproject.toml`):** FastAPI +
Uvicorn (replaces the stdlib `web/app.py` stub; thin I/O handlers, logic stays in
`foo_agent`); **Supabase** Postgres + Auth + RLS (managed; Supabase MCP available
for migrations/types); **Celery + Redis** for MC at scale, proposer grid search,
panel fan-out, and scheduled monitors (jobs must pass `seed`/`as_of` explicitly —
never read the clock); secrets manager for `PARALLEL_API_KEY`/model/aggregation
keys; **structlog + OpenTelemetry + Sentry** with LLM-specific telemetry (prompt
version, model id, tokens, tool calls, guard verdict per turn).

**Data model is immutable by rule:** anything that fed a computed number is
append-only (`profile_version`, `plan_result`, `agent_run`, `audit_log`) — the
DB-level mirror of the engine's reproducibility contract.

**Compliance/security (practical):** SEC Marketing Rule — guard blocks fabricated
performance figures by construction; disclosures auto-attached; advisor approval
before client delivery; retain prompt+output+guard verdict (books & records).
Fiduciary — panel/proposer produce cited rationale + logged approvals. PII — send
Results/structured facts to LLMs, never raw SSNs/documents; redact before external
calls; zero-retention provider terms. SOC2-readiness — hash-chained audit log,
least-privilege roles, KB changes only via reviewed checksummed diffs (the
`research/verify_*` evidence trail), encryption at rest/in transit, backup/DR.

---

## I. Success metrics & verification
- **Correctness:** golden tests for every new module; cross-check tax/estate/SS math
  against published examples; Parallel.ai verification of all dated figures.
- **Determinism preserved:** byte-stable outputs + reproducible MC + guarded AI
  (no AI-introduced numbers) enforced by tests.
- **Product:** advisor can generate a full multi-front plan from a real client's
  documents, see every number's source, get an AI-drafted narrative + expert-panel
  critique + ranked strategy ideas, and approve — end to end.
- **Wedge KPI:** time-to-first-plan and lifetime-tax-saved vs Holistiplan/RightCapital
  on the same inputs.

---

## J. Immediate next actions (on approval)
1. **Commit this doc** to `financial-planning-agent/STRATEGY.md` as the living roadmap.
2. **Correctness track (ship first, days):** fix C1–C10 — MAGI, insight guardrails,
   decumulation ruleset, graduated/state estate, RMDs, SS/taxes in projection, risk
   capacity-vs-tolerance, bootstrap MC, all-state params (Parallel.ai-verified),
   spousal modeling. Highest trust impact; defends the "puts them out of business" claim.
3. **Phase 4 wedge:** build the **Tool/Contract Plane** + **Planning Copilot** — the
   visible "AI-native" leap, low determinism risk, demoable on today's engine.
4. **Phase 5:** persistence + FastAPI + auth to make it a real multi-firm product.

> Open question to confirm at execution time: which **single** Phase-4 deliverable
> to build first if we want one shippable artifact this week — the correctness PR
> (max trust) or the Copilot prototype (max "wow"). Recommendation: correctness PR
> first, Copilot immediately after.
