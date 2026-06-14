export const meta = {
  name: 'financial-experts-gate',
  description: 'Per-chunk Financial-Experts review gate: persona fan-out + adversarial red-team over the chunk diff and PINNED engine output, FAIL-CLOSED aggregation. Advisory findings + machine-checkable blocking conditions.',
  phases: [
    { title: 'Context', detail: 'read rubric + diff, pin real engine output' },
    { title: 'Review', detail: 'one agent per domain persona' },
    { title: 'RedTeam', detail: 'try to refute every blocking finding' },
    { title: 'Report', detail: 'write deterministic gate verdict' },
  ],
}

const REPO = '/Users/bonewitz/foo-planner/financial-planning-agent'
const chunk = (args && args.chunk) || ''
const base = (args && args.base) || 'origin/claude/financial-planning-agent-b5yxqp'
// Deterministic override: the caller SHOULD pass the rubric's block_if_any (read
// from rubrics/<chunk>.yaml in the main thread) so the gate never depends on an
// LLM to decide what can block. If absent, we fall back to the Context agent, and
// if THAT is empty for a chunk with a rubric we return NEEDS_HUMAN (never auto-PASS).
const argBlock = (args && Array.isArray(args.block_if_any)) ? args.block_if_any : null
if (!chunk) throw new Error('financial-experts-gate requires args.chunk, e.g. {chunk:"C03"}')

const PERSONA = {
  tax_cpa: 'a CPA with 30+ years in individual & fiduciary tax (federal/state brackets, NIIT/IRMAA/AMT, Roth math)',
  estate_attorney: 'an estate attorney with 30+ years (IRC 2058, graduated state estate tax, DSUE/GST, step-up basis)',
  cfp_decumulation: 'a CFP retirement-income specialist (RMDs, withdrawal order, Guyton-Klinger guardrails, income floor, sequence risk)',
  risk_quant: 'a CFA risk quant (capacity vs tolerance, CMA / Monte Carlo methodology, glidepath, sequence-of-returns)',
  copilot_safety: 'an AI-safety reviewer for fiduciary copilots (the number guard, no LLM-authored figures, prompt injection, tool fence)',
  intake_correctness: 'a planning-intake correctness reviewer (structured low-friction input, per-answer validation, the NOTE-1 pill / bracket-aware intake)',
  fiduciary_compliance: 'a fiduciary compliance reviewer (disclosures naming material gaps, requires_advisor_review, Reg BI, books-and-records)',
}

const CTX_SCHEMA = { type: 'object', properties: {
  chunk: { type: 'string' },
  personas: { type: 'array', items: { type: 'string' } },
  block_if_any: { type: 'array', items: { type: 'string' } },
  rubric: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, text: { type: 'string' } }, required: ['id', 'text'] } },
  diff_summary: { type: 'string' },
  engine_evidence: { type: 'string' },
}, required: ['chunk', 'personas', 'rubric', 'block_if_any', 'diff_summary'] }

const FINDINGS_SCHEMA = { type: 'object', properties: {
  persona: { type: 'string' },
  verdict: { type: 'string', enum: ['pass', 'block'] },
  findings: { type: 'array', items: { type: 'object', properties: {
    severity: { type: 'string', enum: ['blocking', 'advisory'] },
    rubric_item: { type: 'string' },
    claim: { type: 'string' },
    evidence: { type: 'string' },
  }, required: ['severity', 'rubric_item', 'claim', 'evidence'] } },
}, required: ['persona', 'verdict', 'findings'] }

// RedTeam verdict is paired to a candidate BY INDEX; we deliberately do not key on
// any model-supplied id (a typo'd id must not silently drop a real block).
const VERDICT_SCHEMA = { type: 'object', properties: {
  survives: { type: 'boolean' }, reason: { type: 'string' },
}, required: ['survives'] }

phase('Context')
const ctx = await agent(
  `Assemble the review context for chunk ${chunk} of the foo-agent repo at ${REPO}.\n` +
  `1. Read ${REPO}/tasks.md; find id=${chunk}; extract files[], gates.experts[], expert_rubric.\n` +
  `2. Read ${REPO}/rubrics/${chunk}.yaml; return items as {id,text}[] and block_if_any (the rubric ids that may block) EXACTLY as written.\n` +
  `3. Diff: \`git -C ${REPO} diff ${base}...HEAD -- <files[]>\`; summarize ACTUAL changes citing file:line. If empty, "(no diff)".\n` +
  `4. Pin ENGINE EVIDENCE personas judge against (never their own arithmetic). Run e.g.:\n` +
  `   cd ${REPO} && .venv/bin/python -c "import json,foo_agent; [print(p, foo_agent.plan(json.load(open('tests/golden/profiles/'+p+'.json'))).get('input_hash')) for p in ['young_saver_TX','near_retiree_TX','hnw_estate_NY']]"\n` +
  `   plus chunk-specific behavior. Put real outputs/hashes into engine_evidence.\n` +
  `personas = gates.experts (fall back to [copilot_safety]).`,
  { label: `ctx:${chunk}`, phase: 'Context', schema: CTX_SCHEMA })

if (!ctx) throw new Error('context assembly failed for ' + chunk)
const personas = (ctx.personas && ctx.personas.length) ? ctx.personas : ['copilot_safety']
const rubricText = (ctx.rubric || []).map(r => `${r.id}: ${r.text}`).join('\n')
const rubricIds = new Set((ctx.rubric || []).map(r => r.id))
// Deterministic block list: caller override wins; else Context agent; validated to rubric ids.
let blockIds = (argBlock !== null ? argBlock : (ctx.block_if_any || [])).filter(id => rubricIds.has(id))
const hasRubric = (ctx.rubric || []).length > 0
// FAIL-CLOSED: a chunk with a rubric but no usable block list cannot be auto-approved.
const noBlockSpec = hasRubric && blockIds.length === 0

phase('Review')
const reviews = (await parallel(personas.map(p => () => agent(
  `You are ${PERSONA[p] || p}. Review chunk ${chunk} STRICTLY against the rubric below. ` +
  `Judge the engine's REAL output (provided), never numbers you compute yourself.\n\n` +
  `RUBRIC (judge each YES/NO):\n${rubricText}\n\nDIFF:\n${ctx.diff_summary}\n\nENGINE EVIDENCE:\n${ctx.engine_evidence || '(none)'}\n\n` +
  `Return structured findings. EVERY finding MUST cite evidence (a diff line, file path, or engine output/hash) or it is discarded. ` +
  `Set verdict='block' if you believe this chunk must not merge. Mark a finding 'blocking' if its rubric_item is in [${[...blockIds].join(', ') || 'none'}]; else 'advisory'.`,
  { label: `review:${chunk}:${p}`, phase: 'Review', schema: FINDINGS_SCHEMA })
))).filter(Boolean)

// Candidate blockers: ANY finding (regardless of self-assigned severity) whose
// rubric_item is a real block id AND that carries evidence. Promoting regardless
// of severity stops a single agent downgrading a real defect to 'advisory'.
const candidates = []
for (const r of reviews) for (const f of (r.findings || [])) {
  if (f.evidence && f.evidence.trim() && blockIds.includes(f.rubric_item)) {
    candidates.push({ persona: r.persona, ...f })
  }
}

phase('RedTeam')
let surviving = []
if (candidates.length) {
  const verdicts = await parallel(candidates.map(b => () => agent(
    `Adversarially REFUTE this blocking finding on chunk ${chunk}. Default survives=false unless the evidence is real and on-rubric.\n` +
    `FINDING [${b.rubric_item}] by ${b.persona}: ${b.claim}\nEVIDENCE: ${b.evidence}\n\n` +
    `Verify against the real repo (${REPO}), the diff, and engine evidence:\n${ctx.engine_evidence || '(none)'}\n` +
    `It SURVIVES only if you cannot refute it with evidence.`,
    { label: `redteam:${chunk}:${b.rubric_item}`, phase: 'RedTeam', schema: VERDICT_SCHEMA })
  ))
  // Pair by INDEX (parallel preserves order). A dead/missing verdict fails CLOSED (survives).
  surviving = candidates.filter((b, i) => { const v = verdicts[i]; return !v || v.survives !== false })
}

const survivingSet = new Set(surviving)
const advisory = []
for (const r of reviews) for (const f of (r.findings || [])) {
  const cand = candidates.find(c => c.persona === r.persona && c.rubric_item === f.rubric_item && c.claim === f.claim)
  if (!cand || !survivingSet.has(cand)) advisory.push({ persona: r.persona, ...f })
}

// Cross-check: an agent's own 'block' verdict with nothing surviving => human, not auto-PASS.
const anyAgentBlock = reviews.some(r => r.verdict === 'block')
let verdict
if (surviving.length) verdict = 'BLOCK'
else if (noBlockSpec || anyAgentBlock) verdict = 'NEEDS_HUMAN'
else verdict = 'PASS'

const report = { chunk, verdict, base, surviving_blocking: surviving, advisory, personas,
  block_if_any: [...blockIds], rubric: ctx.rubric,
  notes: noBlockSpec ? 'no usable block_if_any for a chunk with a rubric -> human adjudication required'
    : (anyAgentBlock && !surviving.length ? 'a reviewer voted block but no finding survived red-team -> human adjudication' : '') }

phase('Report')
await agent(
  `Create dir ${REPO}/artifacts/gates/ if needed and write this gate report as pretty JSON to ` +
  `${REPO}/artifacts/gates/${chunk}.json, then return exactly: "GATE ${chunk}: ${verdict}".\n` +
  '```json\n' + JSON.stringify(report, null, 2) + '\n```',
  { label: `report:${chunk}`, phase: 'Report' })

log(`GATE ${chunk}: ${verdict} — ${surviving.length} surviving blocking, ${advisory.length} advisory`)
return report
