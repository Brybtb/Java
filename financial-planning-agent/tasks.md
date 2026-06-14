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
files: [foo_agent/projection/proposed.py, foo_agent/workflow/orchestrator.py, web/index.html, tests/test_proposed.py]
dod:
  - "map recommendations to a scenario, apply_scenario, re-run plan; return baseline + proposed + per-rec delta"
  - "deltas shown for funded_ratio and P(success); deterministic"
gates: { code: required, ui: smoke, experts: [cfp_decumulation, risk_quant, tax_cpa] }
expert_rubric: rubrics/C04.yaml
status: todo
```
```yaml
id: C05
title: pill / bracket-aware intake (NOTE-1)
tier: "10^3"
depends_on: [C03]
files: [web/index.html, web/app.py, tests/test_web_app.py]
dod:
  - "filing-status pills; income-band pills from TY2026 brackets for chosen filing status (re-render on change)"
  - "state picker; visible progress counter; chat demoted to fallback"
  - "new GET /api/intake/brackets reuses rules.loader.load_params"
gates: { code: required, ui: required, experts: [intake_correctness, tax_cpa] }
expert_rubric: rubrics/C05.yaml
status: todo
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
