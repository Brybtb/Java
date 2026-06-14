# tasks.md — foo-agent build tracker (source of truth)

One fenced `yaml` block per chunk (machine-parsed by `tools/scope_fence.py` and the
`financial-experts-gate` workflow). status: todo | in_progress | done | blocked.
Run the gate: `Workflow({scriptPath: ".claude/workflows/financial-experts-gate.js", args:{chunk:"C03"}})`.

## Phase 0 — safety net

```yaml
id: P0-CI
title: CI workflow + test network fence
tier: "10^0"
files: [.github/workflows/ci.yml, tests/conftest.py]
gates: { code: required, ui: skip, experts: [] }
status: done
```
```yaml
id: P0-DOC
title: doc-drift guard + fix CLAUDE.md model string
tier: "10^0"
files: [tests/test_doc_consistency.py, CLAUDE.md]
gates: { code: required, ui: skip, experts: [] }
status: done
```
```yaml
id: P0-CLOCK
title: invert no_clock guard to denylist-by-default
tier: "10^0"
files: [tests/test_no_clock.py]
gates: { code: required, ui: skip, experts: [] }
status: done
```
```yaml
id: P0-GOLD
title: structured golden diff + WHY-gated regen
tier: "10^0"
files: [tests/_golden_util.py, tests/test_golden.py]
gates: { code: required, ui: skip, experts: [] }
status: done
```
```yaml
id: P0-GATE
title: financial-experts-gate workflow + tasks.md + rubrics + scope fence
tier: "10^0"
files:
  - .claude/workflows/financial-experts-gate.js
  - .claude/skills/financial-experts-gate/SKILL.md
  - tasks.md
  - rubrics/_template.yaml
  - rubrics/C01.yaml
  - rubrics/C03.yaml
  - tools/__init__.py
  - tools/scope_fence.py
  - tests/test_scope_fence.py
gates: { code: required, ui: skip, experts: [] }
status: done
```

## 10^0 — hygiene (audit B7-B18, D1b/D2/D3)

```yaml
id: C00
title: hygiene batch A (B13 null, B10 errors->400, B11 NaN/Inf, D2 honest llm_active, D3 sanitized errors, D1b drop Bearer)
tier: "10^0"
depends_on: [P0-GATE]
files: [web/app.py, foo_agent/agents/llm.py, foo_agent/agents/copilot.py, tests/test_web_app.py, tasks.md, rubrics/C00.yaml]
dod:
  - "POST with profile:null -> 200 collecting, not 500"
  - "validation errors (bad enum/date/string income/missing schema_version) -> 400 with sanitized message"
  - "NaN/Infinity rejected at the money boundary"
  - "llm_active true only after a successful guarded turn"
  - "no raw provider/server error body reaches the client"
  - "Bearer-OAuth fallback removed from llm.py"
tests_to_add: [test_profile_null_does_not_500, test_invalid_enum_returns_400, test_nonfinite_rejected_400, test_llm_active_false_without_llm, test_500_is_sanitized, test_llm_uses_api_key_header_not_bearer]
gates: { code: required, ui: skip, experts: [copilot_safety, fiduciary_compliance] }
expert_rubric: rubrics/C00.yaml
status: done
```
```yaml
id: C01
title: guard hardening (B7) - value allowlist, drop whole-blob whitelist
tier: "10^0"
depends_on: [P0-GATE]
files: [foo_agent/explain/guard.py, tests/test_agents.py, tasks.md]
dod:
  - "allowed-number set built from computed dollars/%/ages only"
  - "provenance values (hashes, seeds, as_of, indices) are NOT allowed numbers"
  - "fabricated $2026 / $409938 / spelled-out figures are rejected"
  - "all existing guard tests still pass"
tests_to_add: [test_guard_rejects_provenance_collision, test_guard_rejects_spelled_out]
gates: { code: required, ui: skip, experts: [copilot_safety] }
expert_rubric: rubrics/C01.yaml
status: done
```
```yaml
id: C02
title: DoS/limits/clamps (B9 timeout+413, B12 deferral bound, B17 PDF epoch, B16 DOM-escape, B8 funded_ratio clamp, B15 per-answer validation)
tier: "10^0"
depends_on: [P0-GATE]
files: [web/app.py, web/index.html, foo_agent/calculators/contributions.py, foo_agent/report/pdf.py, foo_agent/agents/copilot.py, tests/test_web_app.py]
gates: { code: required, ui: smoke, experts: [copilot_safety, risk_quant] }
expert_rubric: rubrics/C02.yaml
status: todo
```

## wedge — make the engine act

```yaml
id: C03
title: set_profile_fields write tool + forward-threaded copilot loop
tier: "10^1"
depends_on: [C01]
files: [foo_agent/agents/engine_tools.py, foo_agent/agents/copilot.py, tests/test_agents.py, tasks.md]
dod:
  - "set_profile_fields(profile, {dotted_path: value}) coerces by interview question type and validates at the contract boundary (B15)"
  - "_llm_turn threads the UPDATED profile forward each iteration (not args.setdefault('profile', entry_profile)) (B1)"
  - "loop overflow returns the deterministic next_question; never raises -> no HTTP 500 (D6)"
  - "a stubbed-LLM conversation builds a full profile from empty and reaches status=ready"
tests_to_add: [test_set_profile_fields_coerces_and_validates, test_llm_turn_threads_profile_forward, test_llm_turn_reaches_ready_from_empty, test_llm_turn_overflow_falls_back_not_raises]
gates: { code: required, ui: skip, experts: [copilot_safety, intake_correctness] }
expert_rubric: rubrics/C03.yaml
status: in_progress
```
```yaml
id: C04
title: current-vs-proposed plan engine
tier: "10^2"
depends_on: [C03]
files: [foo_agent/projection/proposed.py, foo_agent/workflow/orchestrator.py, web/index.html, tests/test_proposed.py, tasks.md, rubrics/C04.yaml]
dod:
  - "map recommendations to a scenario, apply_scenario, re-run plan; return baseline + proposed + per-rec delta"
  - "deltas shown for funded_ratio and P(success); deterministic"
  - "only recommendations whose action edits a projection-consumed field are modeled; the rest are advisory with an honest reason (no fabricated delta)"
tests_to_add: [test_build_returns_baseline_proposed_delta, test_employer_match_is_modeled_and_lifts_funded_ratio, test_advisory_recs_carry_zero_delta_and_a_reason, test_debt_and_protection_are_advisory_not_modeled, test_multiple_modeled_steps_compose, test_waterfall_steps_sum_to_total_delta, test_no_modeled_recs_means_zero_delta, test_proposed_scenario_and_profile_validate, test_proposed_is_deterministic, test_orchestrator_attaches_proposed_when_ready, test_orchestrator_propose_false_omits_it]
gates: { code: required, ui: smoke, experts: [cfp_decumulation, risk_quant, tax_cpa] }
expert_rubric: rubrics/C04.yaml
status: done
```
```yaml
id: C05
title: pill / bracket-aware intake (NOTE-1)
tier: "10^3"
depends_on: [C03]
files: [web/index.html, web/app.py, tests/test_web_app.py, tasks.md, rubrics/C05.yaml]
dod:
  - "filing-status pills; income-band pills from TY2026 brackets for chosen filing status (re-render on change)"
  - "state picker; visible progress counter; chat demoted to fallback"
  - "new GET /api/intake/brackets reuses rules.loader.load_params"
tests_to_add: [test_intake_brackets_single_bands_are_gross_and_dated, test_intake_brackets_rates_match_engine_params, test_intake_brackets_filing_status_changes_bands, test_intake_brackets_endpoint_200, test_intake_brackets_bad_filing_status_400, test_intake_brackets_missing_filing_status_400, test_intake_brackets_unknown_path_404]
gates: { code: required, ui: required, experts: [intake_correctness, tax_cpa] }
expert_rubric: rubrics/C05.yaml
status: done
```
```yaml
id: C06
title: web UI to PDF parity (charts, optimizer tables, sources)
tier: "10^3"
depends_on: [C04]
files: [web/index.html, web/app.py]
dod:
  - "on-screen projection chart, Monte Carlo cone, Asset-Map, recommendation detail, optimizer tables, clickable sources"
gates: { code: required, ui: required, experts: [risk_quant, cfp_decumulation] }
expert_rubric: rubrics/C06.yaml
status: todo
```

## tax-aware multi-bucket (owner direction 2026-06-14): keep more, grow longer, least tax drag

Inversion / end-in-mind: the single-bucket projection (projection/accounts.py blends all
balances into one pot + one blended retirement tax rate) cannot price the difference between
taxable, tax-deferred, and Roth money — so C04 honestly flags taxable-surplus / Roth-vs-pretax
recs as advisory. These three chunks make the engine bucket-aware end to end. Split because the
change is far over the ~400-LOC chunk cap.

```yaml
id: C07
title: multi-bucket accumulation (taxable / tax-deferred / Roth + HSA), per-bucket growth & tax drag
tier: "10^2"
depends_on: [C04]
files: [foo_agent/projection/buckets.py, foo_agent/projection/accounts.py, foo_agent/projection/cashflow.py, foo_agent/montecarlo/simulator.py, foo_agent/montecarlo/cma.py, foo_agent/rules/data/assumptions/cma.2026.yaml, tests/test_buckets.py, tests/golden/expected/young_saver_TX.projection.json, tests/golden/GOLDEN_CHANGELOG.md, tasks.md, rubrics/C07.yaml]
dod:
  - "PlanInputs splits initial_balance + annual_contribution into 3 buckets: taxable, tax_deferred (pre-tax 401k/trad IRA), tax_free (Roth IRA/Roth 401k); HSA folded into tax_free for retirement use"
  - "coexisting contributions route correctly: a Roth IRA + a pre-tax 401k + employer match land in the right buckets simultaneously"
  - "taxable bucket nets an annual tax drag on growth (dividends/turnover); tax-deferred & Roth compound untaxed; deterministic, seeded"
  - "projection + Monte Carlo track the 3 balances and sum to today's single-bucket total when tax treatment is neutralized (golden parity guard) -> any golden change carries a WHY"
tests_to_add: [test_balances_route_to_the_right_buckets, test_contributions_route_pretax_401k_and_match_vs_roth_and_hsa, test_drag_zero_makes_bucket_placement_irrelevant_parity, test_taxable_drag_lowers_taxable_bucket_growth, test_projection_reports_buckets_that_sum_to_balance_at_retirement, test_young_saver_has_no_taxable_bucket, test_projection_is_deterministic]
gates: { code: required, ui: skip, experts: [tax_cpa, risk_quant, cfp_decumulation] }
expert_rubric: rubrics/C07.yaml
status: in_progress
```
```yaml
id: C08
title: tax-aware decumulation (drawdown order, RMDs, bracket-fill / Roth-conversion gap, lifetime tax)
tier: "10^2"
depends_on: [C07]
files: [foo_agent/projection/decumulation.py, foo_agent/projection/__init__.py, tests/test_decumulation_proj.py, tasks.md, rubrics/C08.yaml]
dod:
  - "retirement spend is sourced in tax-efficient order (taxable -> tax-deferred -> Roth) honoring RMDs at the statutory age"
  - "low-bracket headroom filled with tax-deferred withdrawals / partial Roth conversions in the gap years (reuse magi.py + tax.py brackets)"
  - "each retirement year computes ordinary + LTCG tax -> net spendable; output carries lifetime_tax_paid and after-tax terminal wealth"
  - "deterministic; reuses optimize/withdrawal_plan + decum.* rules; a worked-example test verifies the tax math against hand calc"
  - "additive: exposed as projection.decumulation_projection(); project()/funded_ratio unchanged (no golden churn)"
tests_to_add: [test_ordinary_tax_progressive_hand_calc, test_marginal_rate_picks_the_right_bracket, test_schedule_spans_retirement_and_is_deterministic, test_taxable_drains_before_roth_is_touched, test_rmd_is_forced_at_statutory_age, test_rmd_start_age_73_for_pre_1960, test_lifetime_tax_is_nonneg_and_after_tax_terminal_discounts_tax_deferred, test_lifetime_tax_equals_sum_of_yearly_taxes, test_no_taxable_bucket_means_no_ltcg_tax, test_decumulation_projection_from_profile]
gates: { code: required, ui: skip, experts: [tax_cpa, cfp_decumulation, risk_quant] }
expert_rubric: rubrics/C08.yaml
status: done
```
```yaml
id: C10
title: verify + cite the tax/CMA assumptions (Parallel.ai) — SS 85%, LTCG, RMD, taxable_drag, blended rate
tier: "10^1"
depends_on: [C08]
files: [foo_agent/rules/data/citations/sources.json, foo_agent/projection/decumulation.py, foo_agent/rules/data/assumptions/cma.2026.yaml, tests/test_assumption_citations.py, tasks.md, rubrics/C10.yaml]
dod:
  - "every tax/CMA assumption cites a source that resolves in sources.json (fail-closed test)"
  - "sourced values match authority: SS max 85% (IRC 86 / Pub 915), LTCG 0/15/20 (Topic 409), RMD 73/75 + Uniform Lifetime (Pub 590-B)"
  - "researched via Parallel.ai (not ad-hoc web); decumulation output carries assumptions.citations; no new math (no golden churn)"
tests_to_add: [test_decumulation_assumption_citations_resolve, test_cma_tax_assumptions_are_cited, test_sourced_values_match_authority, test_decumulate_output_carries_citations]
gates: { code: required, ui: skip, experts: [tax_cpa, fiduciary_compliance] }
expert_rubric: rubrics/C10.yaml
status: done
```
```yaml
id: C11
title: cross-execute the engine's tax math against an independent oracle (tenforty / OpenTaxSolver)
tier: "10^1"
depends_on: [C08]
files: [pyproject.toml, tests/test_tax_oracle.py, tasks.md, rubrics/C11.yaml]
dod:
  - "engine ordinary_tax matches tenforty to the dollar where the IRS exact worksheet applies (taxable >= 100k), within tax-table rounding below it, across single + MFJ and a range of incomes"
  - "tenforty is an optional [oracle] extra; the test importorskips so CI stays green; documented how to run locally"
tests_to_add: [test_engine_ordinary_tax_matches_tenforty, test_engine_matches_tenforty_taxable_income]
gates: { code: required, ui: skip, experts: [tax_cpa, fiduciary_compliance] }
expert_rubric: rubrics/C11.yaml
status: in_progress
```
```yaml
id: C09
title: asset-location + decumulation surface; un-strand C04 advisory rows (taxable/Roth routing become modeled)
tier: "10^3"
depends_on: [C08]
files: [foo_agent/projection/proposed.py, foo_agent/projection/buckets.py, foo_agent/agents/engine_tools.py, web/index.html, tests/test_proposed.py, tasks.md, rubrics/C09.yaml]
dod:
  - "proposed.py: taxable.hyper_accumulate becomes MODELED now that buckets exist (advisory reason removed); lifetime-tax + after-tax-terminal deltas shown alongside funded_ratio/P(success)"
  - "web shows the bucket breakdown, the year-by-year drawdown/tax schedule, Roth-conversion windows, and least-tax-drag next-dollar guidance"
  - "deltas + decumulation are deterministic and guarded; no fabricated tax numbers; decumulation tool exposed on the engine-tool plane"
tests_to_add: [test_taxable_surplus_is_now_modeled, test_no_modeled_recs_means_zero_delta, test_proposed_carries_decumulation_delta, test_decumulation_tool_is_callable]
gates: { code: required, ui: required, experts: [tax_cpa, cfp_decumulation, risk_quant] }
expert_rubric: rubrics/C09.yaml
status: in_progress
```
