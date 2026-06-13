# SETUP — Hybrid Coding-LLM Stack for Claude Code (automatable)

Goal: maximum quality under a low monthly cap for a **~1B tokens/mo, ~92% cache-hit, ~100 req/day**
profile. This sets up a **flat-rate primary (MiniMax)** + **cache-cheap overflow (DeepSeek)** +
**model breadth (OpenCode Go)**, all driving **Claude Code** through Anthropic-compatible endpoints.

> These steps are written to be executed by an agent in a terminal. Each provider is a self-contained
> block. Secrets come from env vars — never hard-code keys. Validate after each switch.

---

## 0. Prerequisites (run once)

```bash
# Claude Code present?
claude --version || npm install -g @anthropic-ai/claude-code

# jq + curl for validation
command -v jq curl >/dev/null || { sudo apt-get update && sudo apt-get install -y jq curl; }

# A profile dir for per-provider env files
mkdir -p ~/.config/cc-providers
```

Create `~/.config/cc-providers/keys.env` (chmod 600) and fill in your keys — DO NOT COMMIT IT:

```bash
cat > ~/.config/cc-providers/keys.env <<'EOF'
# Fill these in. Leave blank the ones you don't use.
export MINIMAX_API_KEY=""      # sk-cp... from platform.minimax.io (Token Plan subscription key)
export DEEPSEEK_API_KEY=""     # from platform.deepseek.com
export OPENCODE_GO_KEY=""      # from opencode.ai/go subscription
export MOONSHOT_API_KEY=""     # optional, Kimi Code: platform.kimi.ai
export OPENROUTER_API_KEY=""   # optional fallback: openrouter.ai/keys
EOF
chmod 600 ~/.config/cc-providers/keys.env
```

---

## 1. PRIMARY — MiniMax Token Plan ($20/mo Plus, ~1.7B M3 tokens)

Subscribe at platform.minimax.io/subscribe/token-plan → get the **`sk-cp...` subscription key**.
MiniMax exposes an **Anthropic-compatible endpoint**, so Claude Code drives M3 directly.

```bash
cat > ~/.config/cc-providers/minimax.env <<'EOF'
source ~/.config/cc-providers/keys.env
export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
export ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY"
export ANTHROPIC_MODEL="MiniMax-M3"
export ANTHROPIC_DEFAULT_OPUS_MODEL="MiniMax-M3"
export ANTHROPIC_DEFAULT_SONNET_MODEL="MiniMax-M3"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="MiniMax-M3"
export ANTHROPIC_SMALL_FAST_MODEL="MiniMax-M3"
EOF
```
> NOTE: Confirm the exact base URL + model id against MiniMax's current "Token Plan / Claude Code"
> docs at setup time (vendors rename models, e.g. M3 → M3.x). The `subscribe/token-plan` page and
> docs list the live endpoint and the `sk-cp` key flow.

Launch with MiniMax:
```bash
bash -c 'source ~/.config/cc-providers/minimax.env && claude'
```

---

## 2. OVERFLOW — DeepSeek API direct (cache-hit champion)

DeepSeek serves a native **Anthropic-compatible API**; cache-hit input is ~$0.07/M (V4 Flash),
which is ideal for a 92%-cache workload.

```bash
cat > ~/.config/cc-providers/deepseek.env <<'EOF'
source ~/.config/cc-providers/keys.env
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_API_KEY"
export ANTHROPIC_MODEL="deepseek-chat"
export ANTHROPIC_DEFAULT_OPUS_MODEL="deepseek-chat"
export ANTHROPIC_DEFAULT_SONNET_MODEL="deepseek-chat"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="deepseek-chat"
export ANTHROPIC_SMALL_FAST_MODEL="deepseek-chat"
EOF
```
Launch with DeepSeek:
```bash
bash -c 'source ~/.config/cc-providers/deepseek.env && claude'
```
> Cost control: cache-hit input is near-free; **output dominates your bill** — keep responses tight.
> DeepSeek also has off-peak discount windows; batch heavy jobs there if latency-tolerant.

---

## 3. BREADTH — OpenCode Go ($10/mo, ~12–14 open models, any agent)

Subscribe at opencode.ai/go → get the Go API key. Two ways to use it:

**(a) Inside the OpenCode agent (native):**
```bash
command -v opencode >/dev/null || curl -fsSL https://opencode.ai/install | bash
opencode auth login        # choose "OpenCode Go", paste $OPENCODE_GO_KEY
opencode                   # then pick DeepSeek V4 Pro / GLM-5.1 / Kimi K2.6 / MiniMax M3 etc.
```

**(b) From Claude Code via the OpenCode Zen OpenAI-compatible gateway** (see Zen docs for current
base URL/model ids; route through LiteLLM if you want one Anthropic endpoint for everything — §5).

---

## 4. OPTIONAL — Kimi Code (best Claude Code citizen, +75% cache discount)

If you want Kimi K2.7 Code (NOT the "Moderato" chat membership): subscribe to **Kimi Code** at
platform.kimi.ai, then:

```bash
cat > ~/.config/cc-providers/kimi.env <<'EOF'
source ~/.config/cc-providers/keys.env
export ANTHROPIC_BASE_URL="https://api.moonshot.ai/anthropic"
export ANTHROPIC_AUTH_TOKEN="$MOONSHOT_API_KEY"
export ANTHROPIC_MODEL="kimi-k2.7-code"
export ANTHROPIC_DEFAULT_OPUS_MODEL="kimi-k2.7-code"
export ANTHROPIC_DEFAULT_SONNET_MODEL="kimi-k2.7-code"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="kimi-k2.7-code"
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=262144
export ENABLE_TOOL_SEARCH=false
EOF
bash -c 'source ~/.config/cc-providers/kimi.env && claude'
```
(Endpoint + model id are from Moonshot's official "Use Kimi in Claude Code" doc.)

---

## 5. RECOMMENDED GLUE — one gateway, many models (LiteLLM or claude-code-router)

To switch models without re-exporting env, run a local gateway that speaks the **Anthropic Messages
API** and routes to all providers. Two proven options:

**A) claude-code-router** (purpose-built for Claude Code):
```bash
npm install -g @musistudio/claude-code-router   # package name per its GitHub README at install time
# Configure ~/.claude-code-router/config.json with providers: minimax, deepseek, opencode, kimi, openrouter
# Then point Claude Code at the local router:
export ANTHROPIC_BASE_URL="http://127.0.0.1:3456"
claude
```

**B) LiteLLM proxy** (serves `/v1/messages`):
```bash
pip install 'litellm[proxy]'
# litellm --config litellm.config.yaml  (map model aliases -> minimax/deepseek/openrouter/kimi)
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
export CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1   # let Claude Code list gateway models
claude
```
This gives one endpoint, model-switch on the fly, and provider sticky routing to maximize cache hits.

---

## 6. Helper — a `ccp` switcher function

```bash
cat >> ~/.bashrc <<'EOF'
ccp() {  # ccp <minimax|deepseek|kimi>  -> launch Claude Code on that provider
  local p="${1:-minimax}"
  local f="$HOME/.config/cc-providers/${p}.env"
  [ -f "$f" ] || { echo "no profile: $f"; return 1; }
  ( source "$f"; echo "Claude Code -> $p ($ANTHROPIC_MODEL)"; claude )
}
EOF
echo "Reload: source ~/.bashrc ; then:  ccp minimax | ccp deepseek | ccp kimi"
```

---

## 7. Validation (run after each provider setup)

```bash
# Generic Anthropic-compatible smoke test (works for any provider block above)
validate() {  # validate <base_url> <token> <model>
  curl -sS "$1/v1/messages" \
    -H "x-api-key: $2" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d "{\"model\":\"$3\",\"max_tokens\":16,\"messages\":[{\"role\":\"user\",\"content\":\"say OK\"}]}" \
    | jq -r '.content[0].text // .error.message // "no parse"'
}
# Example:
# source ~/.config/cc-providers/deepseek.env && validate "$ANTHROPIC_BASE_URL" "$ANTHROPIC_AUTH_TOKEN" "$ANTHROPIC_MODEL"
```
Expected: prints `OK` (or similar). An auth/endpoint error prints the provider's message instead.

---

## 8. Recommended monthly operating posture

| Layer | Provider | Why | ~Cost |
|---|---|---|---|
| Workhorse | MiniMax Token Plan **Plus** | flat ~1.7B M3 tokens, native CC, frontier coding | **$20** |
| Overflow | DeepSeek direct | cache-hit ~$0.07/M; output-only bill at your 92% cache | ~$5–15 |
| Breadth | OpenCode Go | 12–14 open models, one key, model-hopping | **$10** |
| Anchor (optional) | ChatGPT Plus/Codex | best quality for hard problems, within weekly caps | $20 |
| Glue | claude-code-router / LiteLLM | one endpoint, switch + sticky cache routing | $0 |

**Total core: ~$30–45/mo** for frontier-class coding at ~1B tokens/mo — the "max quality without
hitting limits" balance you asked for. Start with MiniMax + DeepSeek; add the rest as needed.

> [!warning] Verify live values at setup
> Model ids, exact base URLs, prices, and quotas change monthly in this market. Before automating,
> re-confirm each provider's current "Claude Code / Anthropic-compatible" doc page and price table.
> All figures here are sourced as of 2026-06-13 (see REPORT.md citations).
