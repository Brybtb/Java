export const meta = {
  name: 'financial-experts-gate',
  description: 'Per-chunk Financial-Experts review gate: persona fan-out + adversarial red-team over the chunk diff and PINNED engine output, deterministic aggregation. Advisory findings + machine-checkable blocking conditions.',
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
if (!chunk) throw new Error('financial-experts-gate requires args.chunk, e.g. {chunk:"C03"}')

// Persona pool. The chunk's rubric (gates.experts) selects which run.
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
}, required: ['chunk', 'personas', 'rubric', 'diff_summary'] }

const FINDINGS_SCHEMA = { type: 'object', properties: {
  persona: { type: 'string' },
  verdict: { type: 'string', enum: ['pass', 'block'] },
  findings: { type: 'array', items: { type: 'object', properties: {
    severity: { type: 'string', enum: ['blocking', 'advisory'] },
    rubric_item: { type: 'string' },
    claim: { type: 'string' },
    evidence: { type: 'string' },
  }, required: ['severity', 'rubric_item', 'claim', 'evidence'] } },
  confidence: { type: 'number' },
}, required: ['persona', 'verdict', 'findings'] }

const VERDICT_SCHEMA = { type: 'object', properties: {
  rubric_item: { type: 'string' }, survives: { type: 'boolean' }, reason: { type: 'string' },
}, required: ['rubric_item', 'survives'] }

phase('Context')
const ctx = await agent(
  `Assemble the review context for chunk ${chunk} of the foo-agent repo at ${REPO}.\n` +
  `1. Read ${REPO}/tasks.md; find the chunk with id=${chunk}; extract files[], gates.experts[], expert_rubric.\n` +
  `2. Read ${REPO}/rubrics/${chunk}.yaml; return its items as {id,text}[] and block_if_any (the rubric ids that may block).\n` +
  `3. Diff: run \`git -C ${REPO} diff ${base}...HEAD -- <files[]>\` and summarize the ACTUAL changes, citing file:line. If empty, say "(no diff)".\n` +
  `4. Pin ENGINE EVIDENCE the personas must judge against (so they never compute numbers themselves). Run, e.g.:\n` +
  `   cd ${REPO} && .venv/bin/python -c "import json,foo_agent; [print(p, foo_agent.plan(json.load(open('tests/golden/profiles/'+p+'.json'))).get('input_hash')) for p in ['young_saver_TX','near_retiree_TX','hnw_estate_NY']]"\n` +
  `   plus any chunk-specific behavior (curl a locally-run web/app.py if the chunk touches it). Put real outputs/hashes into engine_evidence.\n` +
  `personas = gates.experts from tasks.md (fall back to [copilot_safety] if none).`,
  { label: `ctx:${chunk}`, phase: 'Context', schema: CTX_SCHEMA })

if (!ctx) throw new Error('context assembly failed for ' + chunk)
const personas = (ctx.personas && ctx.personas.length) ? ctx.personas : ['copilot_safety']
const rubricText = (ctx.rubric || []).map(r => `${r.id}: ${r.text}`).join('\n')
const blockIds = ctx.block_if_any || []

phase('Review')
const reviews = (await parallel(personas.map(p => () => agent(
  `You are ${PERSONA[p] || p}. Review chunk ${chunk} STRICTLY against the rubric below. ` +
  `Judge the engine's REAL output (provided), never numbers you compute yourself.\n\n` +
  `RUBRIC (judge each YES/NO):\n${rubricText}\n\nDIFF:\n${ctx.diff_summary}\n\nENGINE EVIDENCE:\n${ctx.engine_evidence || '(none)'}\n\n` +
  `Return structured findings. EVERY finding MUST cite evidence (a diff line, file path, or engine output/hash) or it is discarded. ` +
  `Mark 'blocking' ONLY if its rubric_item is one of [${blockIds.join(', ') || 'none'}]; else 'advisory'.`,
  { label: `review:${chunk}:${p}`, phase: 'Review', schema: FINDINGS_SCHEMA })
))).filter(Boolean)

// Collect candidate blocking findings: blocking severity + on the block list + has evidence.
const candidates = []
for (const r of reviews) for (const f of (r.findings || [])) {
  if (f.severity === 'blocking' && f.evidence && f.evidence.trim() && blockIds.includes(f.rubric_item)) {
    candidates.push({ persona: r.persona, ...f })
  }
}

phase('RedTeam')
let surviving = []
if (candidates.length) {
  const verdicts = (await parallel(candidates.map(b => () => agent(
    `Adversarially REFUTE this blocking finding on chunk ${chunk}. Default survives=false unless the evidence is real and on-rubric.\n` +
    `FINDING [${b.rubric_item}] by ${b.persona}: ${b.claim}\nEVIDENCE: ${b.evidence}\n\n` +
    `Verify against the real repo (${REPO}), the diff, and engine evidence:\n${ctx.engine_evidence || '(none)'}\n` +
    `It SURVIVES only if you cannot refute it with evidence.`,
    { label: `redteam:${chunk}:${b.rubric_item}`, phase: 'RedTeam', schema: VERDICT_SCHEMA })
  ))).filter(Boolean)
  const live = new Set(verdicts.filter(v => v.survives).map(v => v.rubric_item))
  surviving = candidates.filter(b => live.has(b.rubric_item))
}

// Advisory = everything that is not a surviving block.
const survivingItems = new Set(surviving.map(b => b.rubric_item))
const advisory = []
for (const r of reviews) for (const f of (r.findings || [])) {
  if (!(survivingItems.has(f.rubric_item) && f.severity === 'blocking')) advisory.push({ persona: r.persona, ...f })
}

const verdict = surviving.length ? 'BLOCK' : 'PASS'
const report = { chunk, verdict, base, surviving_blocking: surviving, advisory, personas, rubric: ctx.rubric }

phase('Report')
await agent(
  `Create dir ${REPO}/artifacts/gates/ if needed and write this gate report as pretty JSON to ` +
  `${REPO}/artifacts/gates/${chunk}.json, then return exactly: "GATE ${chunk}: ${verdict}".\n` +
  '```json\n' + JSON.stringify(report, null, 2) + '\n```',
  { label: `report:${chunk}`, phase: 'Report' })

log(`GATE ${chunk}: ${verdict} — ${surviving.length} surviving blocking, ${advisory.length} advisory`)
return report
