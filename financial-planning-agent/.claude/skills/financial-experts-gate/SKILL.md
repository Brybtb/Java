---
name: financial-experts-gate
description: Run the per-chunk Financial-Experts review gate for a foo-agent build chunk. Use after a chunk's code gate (pytest) is green and before merging, or when asked to "run the expert gate on <chunk>". Produces cited advisory critiques plus a deterministic blocking verdict.
---

# Financial-Experts gate

The reusable review gate for every product chunk (C00+). It is **read-only on the
repo** — it reviews, it never edits.

## How it works
It is a parameterized Workflow at `.claude/workflows/financial-experts-gate.js`.
Invoke it with the chunk id:

```
Workflow({ scriptPath: ".claude/workflows/financial-experts-gate.js",
           args: { chunk: "C03",
                   block_if_any: ["R1","R2","R4"],                 // authoritative (from rubrics/C03.yaml)
                   rubric: [{ id: "R1", text: "..." }, /* ... */], // optional but recommended
                   personas: ["copilot_safety","intake_correctness"] } })
```

**Pass `block_if_any` (and ideally `rubric`/`diff`/`engine_evidence`) deterministically from the caller** — they are authoritative and remove the LLM from the ground-truth path. Invoke via `scriptPath` (not `name`, which can run a stale registered snapshot). The gate is **fail-closed**: any uncertainty (missing persona, un-adjudicated block item, dropped-evidence fail, empty diff, empty rubric, caller block id absent from the rubric) → `NEEDS_HUMAN`, never a silent PASS.

Pipeline:
1. **Context** — one agent reads the chunk's `tasks.md` row + `rubrics/<chunk>.yaml`,
   computes the diff vs the integration branch, and **pins real engine output**
   (hashes / values) so personas judge actual output, never numbers they compute.
2. **Review** — one agent per persona in the rubric's `personas`
   (`tax_cpa, estate_attorney, cfp_decumulation, risk_quant, copilot_safety,
   intake_correctness, fiduciary_compliance`). Each returns structured findings;
   **a finding with no evidence pointer is discarded** (kills hallucinated objections).
3. **RedTeam** — each candidate blocking finding must survive an adversarial refutation.
4. **Report** — deterministic aggregation written to `artifacts/gates/<chunk>.json`.

## Verdict semantics (advisory + hard machine conditions)
- A finding **BLOCKS** only if: severity `blocking` AND its `rubric_item` is in the
  rubric's `block_if_any` AND it has evidence AND it survives the red-team.
- Everything else is **advisory** — surfaced to the human, who adjudicates the
  un-testable fiduciary judgment.
- The gate verdict is one input to the merge decision; the other hard blockers
  (pytest red, guard regression, missing citation, unexplained golden churn,
  determinism break, scope-fence breach) are checked outside this gate.

## Adding a chunk
Add a `rubrics/<chunk>.yaml` (see `rubrics/_template.yaml`) and set `gates.experts`
in the chunk's `tasks.md` block.
