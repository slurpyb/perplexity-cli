---
name: perplexity-cli-commands
description: Full command syntax, all flags, and worked examples for perplexity-cli search, ask, and chat commands.
---

# perplexity-cli — Command Reference

## `search` — Web Search (no AI answer)

Returns titles, URLs, and snippets. Does **not** generate an AI answer.
Use `ask` or `chat` when you need an AI-synthesized response.

> **OpenRouter fallback:** if Perplexity errors or only `OPENROUTER_API_KEY` is set, `search` is emulated via `perplexity/sonar-pro` chat. `snippet` and `date` are always `null` on this path. See root [SKILL.md](../SKILL.md#setup--do-it-once-then-run-bare-commands) for backend resolution.

### Syntax

```bash
perplexity-cli [GLOBAL] search [QUERY] [OPTIONS]
perplexity-cli [GLOBAL] search --json 'JSON_STRING'
echo 'JSON_STRING' | perplexity-cli [GLOBAL] search
```

### Arguments

| Arg | Required | Description |
|-----|----------|-------------|
| `QUERY` | No* | The search query string. *Optional when using `--json` or stdin. |

### Options

| Flag | Short | Type | Description |
|------|-------|------|-------------|
| `--mode` | `-m` | `web`\|`academic`\|`sec` | Source filter. `web` = general web (default). `academic` = scholarly/peer-reviewed. `sec` = SEC filings and financial documents. |
| `--recency` | `-r` | `hour`\|`day`\|`week`\|`month`\|`year` | Only return results published within this window. |
| `--domains` | `-d` | comma-separated string | Restrict results to these domains. Example: `github.com,stackoverflow.com` |
| `--language` | `-l` | comma-separated ISO 639-1 | Language filter. Example: `en,fr` |
| `--max-results` | `-n` | integer | Maximum number of results to return. |
| `--country` | | ISO 3166-1 alpha-2 | Geo-localize results. Example: `US` |
| `--after` | | `MM/DD/YYYY` | Only return results published after this date. |
| `--before` | | `MM/DD/YYYY` | Only return results published before this date. |
| `--json` | `-j` | JSON string | All parameters as JSON. CLI flags override JSON values. |

### Examples

```bash
# Basic query
perplexity-cli search "Python 3.13 new features"

# Academic mode, filter by recency
perplexity-cli search "climate change mitigation" --mode academic --recency year

# Financial filings
perplexity-cli search "Apple Q3 2025 earnings" --mode sec

# Domain filter + result cap
perplexity-cli search "async rust" --domains "doc.rust-lang.org,blog.rust-lang.org" --max-results 5

# Date range
perplexity-cli search "AI regulation" --after "01/01/2025" --before "04/01/2025"

# Human-readable output (global flag first!)
perplexity-cli --text search "best Python ORMs"

# JSON flag (good for multi-field queries from agents)
perplexity-cli search --json '{"query": "AI governance", "search_mode": "academic", "max_results": 10}'

# Stdin pipe (great for agents building queries programmatically)
echo '{"query": "Rust vs Go performance", "search_domain_filter": ["benchmarksgame.alioth.debian.org"]}' \
  | perplexity-cli search

# Extract just URLs
perplexity-cli search "Python packaging tools" | jq '.results[].url'
```

---

## `ask` — AI Answer (non-streaming)

Sends a question to Perplexity's Chat Completions API. Waits for the full
response, then outputs JSON with the answer, citations, and token usage.

Use `chat` when you want tokens to stream progressively.

### Syntax

```bash
perplexity-cli [GLOBAL] ask [QUESTION] [OPTIONS]
perplexity-cli [GLOBAL] ask --json 'JSON_STRING'
echo 'JSON_STRING' | perplexity-cli [GLOBAL] ask
```

### Arguments

| Arg | Required | Description |
|-----|----------|-------------|
| `QUESTION` | No* | The question to ask. *Optional when using `--json` or stdin. |

### Options

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--model` | `-m` | string | `sonar` | Model to use. See [models/SKILL.md](../models/SKILL.md). |
| `--system` | `-s` | string | — | System prompt. Sets persona/tone/constraints. |
| `--mode` | | `web`\|`academic`\|`sec` | — | Search mode for grounding sources. |
| `--recency` | `-r` | `hour`\|`day`\|`week`\|`month`\|`year` | — | Filter grounding sources by recency. |
| `--domains` | `-d` | comma-separated | — | Restrict grounding to these domains. |
| `--temperature` | `-t` | `0.0`–`2.0` | — | Response randomness. `0.0`–`0.3` = focused. `0.7`+ = creative. |
| `--max-tokens` | | integer | — | Cap on response length in tokens. |
| `--reasoning` | | `minimal`\|`low`\|`medium`\|`high` | — | Reasoning effort. Higher = better for complex questions but slower. |
| `--related` | | flag | off | Include related follow-up questions in output. |
| `--images` | | flag | off | Include image URLs in output when available. |
| `--json` | `-j` | JSON string | — | All parameters as JSON. CLI flags override JSON values. |

### Examples

```bash
# Basic
perplexity-cli ask "What is quantum computing?"

# With model upgrade
perplexity-cli ask "Analyze the CAP theorem tradeoffs" --model sonar-pro

# Max reasoning for a hard question
perplexity-cli ask "Compare Tokio vs async-std for production Rust" \
  --model sonar-reasoning --reasoning high

# Recent sources only
perplexity-cli --text ask "What changed in Python 3.13?" --recency month

# System prompt to control output format
perplexity-cli ask "Top 5 Python ORMs" \
  --system "Respond as a JSON array with keys: name, stars, best_for"

# Restrict grounding to trusted domains
perplexity-cli ask "Rust lifetimes explained" \
  --domains "doc.rust-lang.org,blog.rust-lang.org"

# Get related questions for follow-up
perplexity-cli ask "How does TLS work?" --related | jq '{answer: .content, follow_ups: .related_questions}'

# Full JSON input (agent-preferred for complex structured requests)
perplexity-cli ask --json '{
  "question": "What are the security implications of JWT?",
  "model": "sonar-pro",
  "search_recency_filter": "year",
  "reasoning_effort": "high",
  "system_prompt": "Be precise. Cite CVEs where relevant."
}'

# Extract plain answer text
perplexity-cli ask "What is TLS?" | jq -r '.content'

# Get citations as newline-separated list
perplexity-cli ask "Rust ownership rules" | jq -r '.citations[]'
```

---

## `chat` — Streaming AI Answer

Like `ask` but streams tokens as they arrive.

**Streaming behaviour by output format:**
- `--text` mode: tokens stream to **stdout** in real time. Citations printed to stderr after completion.
- JSON mode (default): tokens stream to **stderr** as progress. Final complete JSON goes to **stdout**.

This means in agent/script usage, you can ignore stderr and capture clean JSON from stdout.

### Syntax

```bash
perplexity-cli [GLOBAL] chat [QUESTION] [OPTIONS]
```

### Options

Same as `ask` minus `--related` and `--images`, plus:

| Flag | Description |
|------|-------------|
| `--no-stream` | Disable streaming; behave exactly like `ask`. |

### Examples

```bash
# Interactive streaming (human-readable, watch it type)
perplexity-cli --text chat "Explain the Rust borrow checker"

# Streaming with better model
perplexity-cli --text chat "Walk me through async Rust" --model sonar-pro

# Agent use: discard streaming progress, capture final JSON
perplexity-cli chat "Explain TLS handshake" 2>/dev/null | jq -r '.content'

# Same as ask (useful to switch without changing the command name)
perplexity-cli chat "What is WebAssembly?" --no-stream

# Pipe final structured output through jq
perplexity-cli chat "Latest Kubernetes release notes" --recency month \
  2>/dev/null | jq '{answer: .content, sources: .citations}'
```

---

## Global Flags Reference

These always go **before** the subcommand:

| Flag | Type | Description |
|------|------|-------------|
| `--text` | flag | Plain text output instead of JSON |
| `--pretty` | flag | Indented JSON output |
| `--api-key` | string | Perplexity API key (overrides `PERPLEXITY_API_KEY` env var) |

```bash
# Correct placement — all before the subcommand
perplexity-cli --text ask "question"
perplexity-cli --pretty search "query"
perplexity-cli --api-key pplx-xxx --text ask "question"
```

## Backend / Auth

**Best practice: configure once** in `~/.config/perplexity-cli/perplexity-cli.json`
(`perplexity_api_key`, `openrouter_api_key`, plus default `model`/`output`/search params),
then run bare commands. See root [SKILL.md](../SKILL.md#setup--do-it-once-then-run-bare-commands).

Each setting resolves with precedence **`CLI flag > env var > config file > built-in default`**:

| Source | Keys it provides |
|---|---|
| `--api-key` flag | Perplexity key only (highest priority) |
| `PERPLEXITY_API_KEY` env | Primary backend (native Perplexity API) |
| `OPENROUTER_API_KEY` env | Fallback backend (routes to `perplexity/sonar*` on OpenRouter) |
| config file | `perplexity_api_key` / `openrouter_api_key` (lowest priority) |

Both keys present (any source) → Perplexity primary, OpenRouter fallback on `401/402/403/408/429/5xx` + network errors. Only OpenRouter → OpenRouter standalone. Neither → exit `2`.
