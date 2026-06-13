---
title: "High-Volume Coding-LLM Access: Build the Right Quality/Quota Balance"
project: llm-coding-stack-research
date: 2026-06-13
profile: "~1B tokens/month, ~92% cache-hit, ~100 requests/day"
engine: "Parallel.ai Search API — 8 objectives + 3 targeted follow-ups, 70+ cited sources"
status: research-complete
---

# Verdict first

**Your plan is *partially* effective — but two of the seven options are mis-framed, and the
single most important variable (your 92% cache-hit rate) changes the ranking completely.**

> [!important] The cache-hit insight that reframes everything
> "92% cache-hit on ~1B tokens" is a **prompt-caching** profile — the hallmark of a coding
> agent (Claude Code / Codex) re-sending a large, stable context every turn. Cache economics
> are NOT uniform across your seven options:
> - **Pay-per-token APIs (DeepSeek)** price cache reads at ~10% of normal input — so a 92%
>   cache-hit workload is *dramatically* cheaper there than the headline rate suggests. [^53][^65]
> - **Subscription "token plans" (MiniMax, MiMo, Kimi)** mostly bill quota on *actual tokens
>   consumed* — a cache hit still spends quota. The cache discount that makes your Anthropic
>   bill cheap does **not** automatically carry over. Verify per-plan before relying on it.
>
> This means the "right balance" is a **hybrid**, not a single subscription.

**Recommended stack (best quality-per-dollar under a low monthly cap):**
1. **Primary subscription:** MiniMax Token Plan **Plus ($20/mo, ~1.7B M3 tokens)** — flat cost,
   genuinely high quota, M3 is frontier-class on coding, native Claude Code support via `sk-cp` key. [^11][^"mm1"]
2. **Cheap overflow / second opinion:** **DeepSeek API direct** (pay-per-token, ~$0.07/M cache-hit
   on V4 Flash, Anthropic-compatible endpoint) — your 92% cache-hit makes this pennies. [^53][^56]
3. **Optional breadth:** **OpenCode Go ($10/mo)** for one-key access to DeepSeek V4 / GLM / Qwen /
   Kimi / MiniMax behind a single subscription, usable from any agent. [^31][^33][^35]

Skip, for your profile: **MiMo "11B credits"** (credits ≠ tokens — see correction) and
**Kimi "Moderato"** (it's a chat/agent membership, not a coding token plan — see correction).

---

## Option-by-option findings (2026 data)

### 1. OpenAI ChatGPT Plus / Codex — $20/mo
- Codex is included on Free, Go, Plus, Pro, Business, Edu, Enterprise; **limits vary by plan**. [^3][^4]
- **On 2026-04-02 OpenAI moved Codex pricing from per-message to token/credit-based**; limits reset
  **weekly**. [^2][^6] Plus is the entry tier; **Pro $200 = 20× Plus usage, Pro $100 = 5×**. [^5]
- Real-world reports of "usage limit reached" on Plus under heavy agent use. [^1]
- **Fit:** Best raw quality, but **Plus quota is the binding constraint for 100 req/day of agentic
  coding.** You'd likely hit weekly caps. Viable as a *quality anchor*, not the workhorse.

### 2. MiniMax Token Plan — ✅ strongest subscription fit
- **Plus = $20/mo → ~1.7B M3 tokens/month**; Max $50 (~1.8B+), Ultra $120 (~7.1B). Quota windows are
  **5-hour rolling + weekly**. [^11][^"mm1"][^"mm2"]
- **M3 is frontier-class:** ~$0.30/M input list, blended as low as ~$0.06/M with cache; strong coding
  benchmarks (M2.7 hit 78% SWE-bench Verified in one review). [^13][^"mm3"]
- **Native Claude Code integration:** grab the `sk-cp` subscription key, drop into Claude Code / Cline /
  any OpenAI-compatible tool — "no API keys needed." [^11]
- **Caveat:** confirm whether cache-hits reduce quota draw; the ~1.7B figure is generous either way.

### 3. Xiaomi MiMo — ⚠️ "11 billion credits" is misleading
- The 11B-credit tier is **Standard ($16/mo)**; tiers are Lite $6 (4.1B), Standard $16 (11B),
  Pro $50 (38B), Max $100 (82B) credits. [^25]
- **Credits are NOT tokens.** Per Xiaomi's own example: **10M cache-miss input tokens ≈ 3,000M credits.**
  [^23] So **11B credits ≈ ~37M cache-miss input-token-equivalents** — roughly *2 orders of magnitude*
  smaller than it sounds, and far below your 1B-token need. (Cache-hit and output convert at different
  rates, so treat this as order-of-magnitude.)
- MiMo-V2.5-Pro is a strong model (57.2% SWE, ahead of Opus 4.6 in one test). [^22] PAYG ~$1/$3 per M. [^21]
- **Fit:** Quality good, but the credit accounting makes the "11B" headline a trap. Not your workhorse.

### 4. Kimi (Moonshot) "Moderato" — ⚠️ wrong product
- **"Moderato" ($19/mo) is the general Kimi *membership* tier — 60 agent credits/mo**, Office/Deep-Research
  features. It is a chat/assistant plan, **not** a high-volume coding token plan. [^"km1"][^"km4"]
- The actual coding products are **Kimi Code** (~$19/mo membership; API billed separately at
  **$0.60/$2.50 per M, +75% cache discount**) and the **Kimi Code Plan** tiers (Andante ¥49,
  ~300–1,200 token-worth per 5h window). [^"km2"][^"km3"]
- **Kimi has first-class Claude Code support**: native `https://api.moonshot.ai/anthropic` endpoint,
  `kimi-k2.7-code` model. [^"kimi-cc"]
- **Fit:** Great model + clean Claude Code path, but pick **Kimi Code**, not Moderato. Good *secondary*.

### 5. OpenCode Go — ✅ good value multiplier ($10/mo)
- **$5 first month, then $10/mo**; bundles ~12–14 open models (DeepSeek V4 Pro, GLM-5.1, Qwen 3.7,
  Kimi K2.6, MiniMax M3/M2.7, MiMo-V2.5-Pro) behind **one subscription key**, usable from **any agent**. [^31][^33][^35]
- It's a flat-rate alternative to OpenRouter's pay-per-token. "2× = $20" as you noted just means two keys'
  worth of quota; one Go sub is usually enough to start. [^31]
- **Fit:** Excellent **breadth-per-dollar** and model-switching. Strong complement to MiniMax.

### 6. OpenRouter, prepaid $20/mo — flexible, not cheapest
- Pure **pay-per-token aggregator**; you load credits and spend them. Free models exist (`:free`),
  paid models unlimited, **500 req/min**. [^44][^45]
- **Supports prompt caching with provider sticky routing** to maximize cache hits — relevant to you,
  but some providers (Anthropic, Alibaba) require enabling cache per-message. [^42]
- **Fit:** Best as a **router/fallback** for model variety; a flat $20 here buys fewer tokens than a
  $20 MiniMax token plan for the same models. Use it for overflow + benchmarking, not as the base.

### 7. DeepSeek API direct — ✅ cache-hit champion
- **deepseek-chat (V4 Flash): cache-hit input $0.07/M, cache-miss $0.27/M, output $1.10/M.**
  V4-Pro promo $0.435/$0.87; V4-Pro regular cache-hit **$0.0145/M**. [^53][^55][^56]
- **Cache-hit input can be ~50× cheaper than cache-miss** — *exactly* your 92%-cache profile. [^56]
- **Anthropic-compatible API** for drop-in Claude Code use. [^56] Off-peak discounts available.
- **Fit:** **The cheapest possible overflow/bulk option for a cache-heavy workload.** Pennies at your volume.

---

## Cost model for YOUR profile (1B tokens/mo, 92% cache-hit)

Assume a coding-agent split of ~800M input (92% cached = 736M hit / 64M miss) + ~200M output.
Illustrative monthly cost, **DeepSeek deepseek-chat direct**:

| Component | Tokens | Rate | Cost |
|---|---|---|---|
| Cache-hit input | 736M | $0.07/M | ~$51.5 |
| Cache-miss input | 64M | $0.27/M | ~$17.3 |
| Output | 200M | $1.10/M | ~$220.0 |
| **Total** | 1B | — | **~$289/mo** |

> [!note] Output dominates — so cap output, not input
> At 92% cache-hit your *input* is already nearly free; **output tokens are the real bill.** Two levers:
> (1) prefer plans that bundle generous flat quota (MiniMax Plus's ~1.7B tokens at $20 absorbs this far
> more cheaply than metered output), and (2) keep responses tight. The hybrid below pushes routine bulk
> onto the **flat-rate MiniMax quota** and uses DeepSeek only for cache-cheap overflow.

**Bottom line on balance:** A **single $20 MiniMax Plus** plan likely covers most of your month at flat
cost; add **DeepSeek direct** for cache-cheap overflow and **OpenCode Go** for model variety — total
**~$30–40/mo** for frontier-ish quality at your volume, versus ~$289+/mo metered or hitting Plus/Codex caps.

---

## Plan-accuracy scorecard

| Your assumption | Reality | Verdict |
|---|---|---|
| OpenAI Plus/Codex $20 viable for volume | Weekly caps; Pro $200 = 20× | 🟡 quality anchor only |
| MiniMax 1.7B tokens/mo | ✅ Plus $20 ≈ 1.7B M3 tokens | ✅ accurate, recommended |
| MiMo 11B **credits** | Credits ≠ tokens; 11B ≈ ~37M cache-miss tokens | ❌ misleading headline |
| Kimi "Moderato" token plan | Moderato = chat membership (60 agent credits); use **Kimi Code** | ❌ wrong product |
| OpenCode Go 2× = $20 | ✅ $10/mo each, flat bundle of open models | ✅ accurate |
| OpenRouter $20 prepaid | ✅ works, pay-per-token, caching supported | 🟡 router/fallback |
| DeepSeek API | ✅ cache-hit $0.07/M — ideal for 92% cache | ✅ accurate, recommended |

See `SETUP.md` for copy-paste, automatable setup instructions for the recommended hybrid.

## Sources
Full deduped registry in `output/sources_latest.json` (+ supplements: `kimi_supplement.json`,
`minimax_supplement.json`, `kimi_moderato.json`). Key citations referenced inline as `[^n]`.
