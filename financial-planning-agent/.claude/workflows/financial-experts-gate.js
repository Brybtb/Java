export const meta = {
  name: 'financial-experts-gate',
  description: 'Per-chunk Financial-Experts review gate. Caller passes deterministic ground truth (rubric, diff, engine evidence, block_if_any) via args; personas review; red-team refutes; FAIL-CLOSED aggregation (any uncertainty -> NEEDS_HUMAN, never silent PASS).',
  phases: [
    { title: 'Context', detail: 'use caller ground truth (or an agent fallback)' },
    { title: 'Review', detail: 'one agent per domain persona' },
    { title: 'RedTeam', detail: 'refute every block-listed failure (evidence required)' },
    { title: 'Report', detail: 'deterministic verdict' },
  ],
}

const REPO = '/Users/bonewitz/foo-planner/financial-planning-agent'
// args may arrive as a JSON string in some harness paths; coerce before reading.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const chunk = A.chunk || ''
const base = A.base || 'origin/claude/financial-planning-agent-b5yxqp'
if (!chunk) throw new Error('financial-experts-gate requires args.chunk, e.g. {chunk:"C03"}')

// The workflow runtime has NO fs/git/engine access, so ground truth cannot be read
// here. The CALLER assembles it in its own process and passes it in — that removes
// the LLM from the ground-truth path (the Context-agent SPOF). Each is optional; a
// missing piece is filled by a Context agent but can only WEAKEN to NEEDS_HUMAN.
const argBlock = Array.isArray(A.block_if_any) ? A.block_if_any : null   // AUTHORITATIVE
const argRubric = Array.isArray(A.rubric) ? A.rubric : null               // [{id,text}]
const argDiff = typeof A.diff === 'string' ? A.diff : null
const argEvidence = typeof A.engine_evidence === 'string' ? A.engine_evidence : null
const argPersonas = Array.isArray(A.personas) ? A.personas : null

const norm = s => String(s == null ? '' : s).trim().toLowerCase()

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
  chunk: { type: 'string' }, personas: { type: 'array', items: { type: 'string' } },
  block_if_any: { type: 'array', items: { type: 'string' } },
  rubric: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, text: { type: 'string' } }, required: ['id', 'text'] } },
  diff_summary: { type: 'string' }, engine_evidence: { type: 'string' },
}, required: ['chunk', 'personas', 'rubric', 'block_if_any', 'diff_summary'] }

const FINDINGS_SCHEMA = { type: 'object', properties: {
  persona: { type: 'string' },
  verdict: { type: 'string', enum: ['pass', 'block'] },
  findings: { type: 'array', items: { type: 'object', properties: {
    rubric_item: { type: 'string' },
    status: { type: 'string', enum: ['pass', 'fail'] },
    severity: { type: 'string', enum: ['blocking', 'advisory'] },
    claim: { type: 'string' }, evidence: { type: 'string' },
  }, required: ['rubric_item', 'status', 'severity', 'claim', 'evidence'] } },
}, required: ['persona', 'verdict', 'findings'] }

// reason REQUIRED: a refutation that drops a real block must justify itself, else the block survives.
const VERDICT_SCHEMA = { type: 'object', properties: {
  survives: { type: 'boolean' }, reason: { type: 'string' },
}, required: ['survives', 'reason'] }

phase('Context')
// Call the Context agent only for pieces the caller did not provide deterministically.
const needContext = !argRubric || argDiff === null
let ctx = { chunk }
if (needContext) {
  ctx = await agent(
    `Assemble review context for chunk ${chunk} of ${REPO}.\n` +
    `1. Read ${REPO}/tasks.md (id=${chunk}) -> files[], gates.experts[], expert_rubric.\n` +
    `2. Read ${REPO}/rubrics/${chunk}.yaml -> items {id,text}[] and block_if_any EXACTLY.\n` +
    `3. git -C ${REPO} diff ${base}...HEAD -- <files[]>; summarize ACTUAL changes citing file:line. If genuinely empty, "(no diff)".\n` +
    `4. Pin ENGINE EVIDENCE: run the engine on the golden profiles and include the real input_hash values.\n` +
    `personas = gates.experts.`,
    { label: `ctx:${chunk}`, phase: 'Context', schema: CTX_SCHEMA })
  if (!ctx) throw new Error('context assembly failed for ' + chunk)
}
if (ctx.chunk && ctx.chunk !== chunk) throw new Error(`Context returned chunk ${ctx.chunk}, expected ${chunk}`)

const personas = (argPersonas && argPersonas.length) ? argPersonas
  : ((ctx.personas && ctx.personas.length) ? ctx.personas : ['copilot_safety'])
const rubric = argRubric || ctx.rubric || []
const rubricIds = new Set(rubric.map(r => r.id))
const rubricText = rubric.map(r => `${r.id}: ${r.text}`).join('\n')
const diffText = argDiff !== null ? argDiff : (ctx.diff_summary || '')
const engineEvidence = argEvidence !== null ? argEvidence : (ctx.engine_evidence || '(none)')
// argBlock is AUTHORITATIVE (caller); only the agent-fallback list is filtered to known rubric ids.
let blockIds = argBlock !== null ? argBlock.slice() : (ctx.block_if_any || []).filter(id => rubricIds.has(id))

// --- Ground-truth guards: every uncertainty becomes a NEEDS_HUMAN reason (never a silent PASS). ---
const reasons = []
if (rubric.length === 0 && personas.length) reasons.push('empty rubric for an expert-reviewed chunk')
if (blockIds.length === 0 && personas.length) reasons.push('no usable block_if_any list')
if (argBlock !== null) { const m = argBlock.filter(id => !rubricIds.has(id)); if (m.length) reasons.push('caller block ids missing from rubric: ' + m.join(',')) }
if (!diffText.trim() || /\(no diff\)/i.test(diffText)) reasons.push('empty diff vs base (base may be stale/already-merged) — cannot auto-approve an unreviewed chunk')

phase('Review')
const reviews = (await parallel(personas.map(p => () => agent(
  `You are ${PERSONA[p] || p}. Review chunk ${chunk} STRICTLY against the rubric. Judge the REAL output below, never numbers you compute.\n\n` +
  `RUBRIC:\n${rubricText}\n\nDIFF:\n${diffText}\n\nENGINE EVIDENCE:\n${engineEvidence}\n\n` +
  `For EACH rubric item return ONE finding: {rubric_item, status('fail' iff VIOLATED else 'pass'), severity('blocking' only for a FAIL on a block-listed item [${blockIds.join(', ') || 'none'}] else 'advisory'), claim, evidence}. ` +
  `EVERY finding MUST cite concrete evidence (diff line / file path / engine output-hash) or it is discarded. A 'pass' CONFIRMS the criterion and can never block; only a 'fail' can. Cover EVERY block-listed item.`,
  { label: `review:${chunk}:${p}`, phase: 'Review', schema: FINDINGS_SCHEMA })
))).filter(Boolean)
if (reviews.length < personas.length) reasons.push(`${personas.length - reviews.length} reviewer(s) failed to return`)

// Block coverage: every block id must be explicitly adjudicated (pass|fail) by a live persona.
const adjudicated = new Set()
for (const r of reviews) for (const f of (r.findings || [])) {
  if (blockIds.includes(f.rubric_item) && (norm(f.status) === 'pass' || norm(f.status) === 'fail')) adjudicated.add(f.rubric_item)
}
const uncovered = blockIds.filter(id => !adjudicated.has(id))
if (uncovered.length) reasons.push('un-adjudicated block items: ' + uncovered.join(','))

// Candidates: a FAILING block-listed item carrying evidence.
const candidates = []
for (const r of reviews) for (const f of (r.findings || [])) {
  if (norm(f.status) === 'fail' && f.evidence && f.evidence.trim() && blockIds.includes(f.rubric_item)) candidates.push({ persona: r.persona, ...f })
}
// A block-listed FAIL with unusable evidence can't be red-teamed -> escalate, never drop.
const droppedBlockFail = reviews.some(r => (r.findings || []).some(f =>
  norm(f.status) === 'fail' && blockIds.includes(f.rubric_item) &&
  !candidates.find(c => c.persona === r.persona && c.rubric_item === f.rubric_item && c.claim === f.claim)))
if (droppedBlockFail) reasons.push('a block-listed FAIL had unusable evidence (cannot evaluate)')

phase('RedTeam')
// Verdict bound to its candidate IN the callback (order-independent). A refutation drops a
// block only if survives===false AND it carries a reason; otherwise the block survives (fail-closed).
const judged = await parallel(candidates.map(b => () =>
  agent(`Adversarially REFUTE this block-listed finding on chunk ${chunk}. Default survives=true; set survives=false ONLY with a concrete evidence-backed reason.\n` +
        `FINDING [${b.rubric_item}] by ${b.persona}: ${b.claim}\nEVIDENCE: ${b.evidence}\n\nDIFF:\n${diffText}\n\nENGINE EVIDENCE:\n${engineEvidence}`,
        { label: `redteam:${chunk}:${b.rubric_item}`, phase: 'RedTeam', schema: VERDICT_SCHEMA })
    .then(v => ({ b, v })).catch(() => ({ b, v: null }))))
const surviving = judged.filter(({ v }) => !(v && v.survives === false && v.reason && v.reason.trim())).map(({ b }) => b)

const survSet = new Set(surviving)
const advisory = []
for (const r of reviews) for (const f of (r.findings || [])) {
  if (norm(f.status) !== 'fail') continue
  const cand = candidates.find(c => c.persona === r.persona && c.rubric_item === f.rubric_item && c.claim === f.claim)
  if (!cand || !survSet.has(cand)) advisory.push({ persona: r.persona, ...f })
}
const passed = reviews.reduce((n, r) => n + (r.findings || []).filter(f => norm(f.status) === 'pass' && f.evidence && f.evidence.trim()).length, 0)

let verdict
if (surviving.length) verdict = 'BLOCK'
else if (reasons.length) verdict = 'NEEDS_HUMAN'
else verdict = 'PASS'

const report = { chunk, verdict, base, surviving_blocking: surviving, advisory, passed, personas,
  block_if_any: blockIds, needs_human_reasons: reasons, rubric }

phase('Report')
await agent(
  `Create ${REPO}/artifacts/gates/ if needed and write this report as pretty JSON to ${REPO}/artifacts/gates/${chunk}.json, ` +
  `then return exactly "GATE ${chunk}: ${verdict}".\n` + '```json\n' + JSON.stringify(report, null, 2) + '\n```',
  { label: `report:${chunk}`, phase: 'Report' })

log(`GATE ${chunk}: ${verdict} — ${surviving.length} blocking, ${advisory.length} advisory, ${passed} passed, ${reasons.length} human-reasons`)
return report
