# perplexity-cli — Agent Reference

> **Installed as:** `perplexity-cli`
> **Auth:** at least one of `PERPLEXITY_API_KEY` or `OPENROUTER_API_KEY` (env vars). `--api-key` only sets the Perplexity key.

---

## ⚠️ CRITICAL: Global flags come BEFORE the subcommand

```bash
# ✅ CORRECT
perplexity-cli --text ask "What is Rust?"
perplexity-cli --pretty search "AI news"
perplexity-cli --api-key sk-xxx ask "question"

# ❌ WRONG — these will silently fail or error
perplexity-cli ask "What is Rust?" --text
perplexity-cli search "AI news" --pretty
```

`--text`, `--pretty`, and `--api-key` are **global options** attached to the
root `perplexity-cli` command, not to individual subcommands. They must always
precede `search`, `ask`, or `chat`.

---

## Commands at a Glance

| Command  | Use for                                | Output        | Streaming |
|----------|----------------------------------------|---------------|-----------|
| `search` | Raw URLs + snippets, no AI answer      | JSON / text   | No        |
| `ask`    | AI answer with citations, full wait    | JSON / text   | No        |
| `chat`   | AI answer, tokens stream as they arrive| JSON / text   | Yes       |

**Default output is compact JSON** — optimal for agents piping to `jq`.

---

## Research Methodology — Read Before Composing Queries

**Many small queries beat one monolithic ask.** A single "compare A vs B vs C and tell me which" produces shallow surface-level output. Several focused queries — followed by reflection on the answers, then a new round of follow-ups based on what surfaced — produce dramatically better synthesis.

**Start broad, circle in.** Hyper-specific opening questions anchor the model to your prompt's bias instead of the actual landscape. Open wide, see what comes back, then narrow on what Round 1 surfaced.

### Loop shape

```
broad ask → reflect on answer → narrower asks on terms/options that surfaced
         → reflect → synthesis ask referencing what you actually learned
```

### Anti-pattern

```bash
# ❌ One big monolithic ask. Single shallow answer, no chance to course-correct,
#    biased by every "and" clause baked into the question.
perplexity-cli ask "Compare PostgreSQL vs MySQL vs SQLite vs CockroachDB \
  for a multi-region SaaS with strong consistency, 10M users, sub-100ms p99 \
  and tell me which one to pick" --model sonar-pro
```

### Pattern

```bash
# Round 1: deliberately broad — what's the actual landscape?
perplexity-cli ask "What database architectures do multi-region SaaS products use in 2026?" \
  --model sonar-pro | jq -r '.content'

# Agent reflects: which architectures showed up? which constraints really drive the choice?
# Then Round 2 — one focused ask per surfaced option / axis:

perplexity-cli ask "How do products handle write conflicts under multi-region active-active Postgres?" \
  --model sonar-pro --recency year | jq -r '.content'

perplexity-cli ask "What latency penalty does CockroachDB serializable isolation add at 10M user scale?" \
  --model sonar-pro --recency year | jq -r '.content'

# Agent reflects again. Round 3 = synthesis using what was actually learned.
perplexity-cli ask "Given <specific findings>, which approach fits <real constraint>?" \
  --model sonar-pro
```

### Rules of thumb

| Situation | What to do |
|---|---|
| Topic unfamiliar | Round 1 must be **deliberately vague**. "What do people use for X?" beats "Should I use Foo or Bar for X?" |
| You think you know the answer | Bias check — phrase Round 1 as if learning the topic for the first time |
| Question has 3+ "and" clauses | Split it. Each clause becomes its own ask. |
| Two queries return overlapping content | Not narrowing enough — make Round 2 sharper based on Round 1 specifics |
| Answer feels generic | Pull a concrete noun/term from the response, ask a follow-up centered on it |

---

## Output Formats (global flags)

```bash
perplexity-cli ask "question"          # compact JSON (default, best for agents)
perplexity-cli --pretty ask "question" # indented JSON
perplexity-cli --text ask "question"   # plain text, citations printed below
```

In `chat` (streaming) + JSON mode: tokens stream to **stderr**, final JSON goes to **stdout**.
In `chat` (streaming) + `--text` mode: tokens stream to **stdout**.

---

## Setup

```bash
# Install
uv pip install -e .          # or: pip install -e .

# At least one API key is required
export PERPLEXITY_API_KEY="pplx-..."        # primary backend; or pass --api-key
export OPENROUTER_API_KEY="sk-or-v1-..."    # fallback backend (also works standalone)
```

### Backend resolution

| Keys present | Behavior |
|---|---|
| `PERPLEXITY_API_KEY` only | Native Perplexity API |
| `OPENROUTER_API_KEY` only | OpenRouter, routes to `perplexity/sonar*` models |
| Both | Perplexity primary; falls back to OpenRouter on `401/402/403/408/429/5xx` + network errors |
| Neither | Exits `2` with help message |

`--api-key` overrides `PERPLEXITY_API_KEY` only. There is no `--api-key` for OpenRouter.

### Fallback caveats

- `search` on the OpenRouter path emulates via `perplexity/sonar-pro` chat completion. Returns `url` + `name` (title); `snippet` and `date` are always `null` (OpenRouter doesn't expose snippet text).
- `chat` streaming fallback only triggers **before the first chunk emits**. Mid-stream errors propagate (no restart, would duplicate stdout).
- `related_questions` is always `[]` on the OpenRouter path (not exposed by OpenRouter).
- All other fields (`content`, `citations`, `usage`) work identically on both backends. JSON output schema unchanged.

---

## `search` — Web Search (raw results)

Returns titles, URLs, and snippets. No AI-generated answer.

```bash
# Basic
perplexity-cli search "Python 3.13 new features"

# With options
perplexity-cli search "climate papers" --mode academic --recency year
perplexity-cli search "AAPL earnings" --mode sec
perplexity-cli search "rust async" --domains "doc.rust-lang.org,blog.rust-lang.org"
perplexity-cli search "news" --recency day --max-results 5 --country US

# Human-readable
perplexity-cli --text search "best Python ORMs"

# JSON input (agent-preferred for complex queries)
perplexity-cli search --json '{"query": "AI news", "search_mode": "web", "max_results": 5}'

# Stdin pipe
echo '{"query": "AI news", "max_results": 3}' | perplexity-cli search
```

### `search` Options

| Flag | Short | Type | Description |
|------|-------|------|-------------|
| `--mode` | `-m` | `web`\|`academic`\|`sec` | Source filter (default: `web`) |
| `--recency` | `-r` | `hour`\|`day`\|`week`\|`month`\|`year` | Recency filter |
| `--domains` | `-d` | comma-separated | Restrict to these domains |
| `--language` | `-l` | ISO 639-1, comma-sep | Language filter (e.g. `en,fr`) |
| `--max-results` | `-n` | int | Max results to return |
| `--country` | | ISO 3166-1 alpha-2 | Geo-localize (e.g. `US`) |
| `--after` | | `MM/DD/YYYY` | Published after date |
| `--before` | | `MM/DD/YYYY` | Published before date |
| `--json` | `-j` | JSON string | Full params as JSON; CLI flags override |

### `search` JSON Input Schema

```json
{
  "query": "string or list of strings",
  "search_mode": "web | academic | sec",
  "search_recency_filter": "hour | day | week | month | year",
  "search_domain_filter": ["domain1.com", "domain2.com"],
  "search_language_filter": ["en", "fr"],
  "max_results": 10,
  "max_tokens": 500,
  "country": "US",
  "search_after_date_filter": "01/01/2024",
  "search_before_date_filter": "12/31/2024"
}
```

### `search` JSON Output Schema

```json
{
  "query": "string",
  "results": [
    {
      "url": "https://...",
      "name": "Page title",
      "snippet": "Relevant excerpt...",
      "date": "2024-01-15"
    }
  ]
}
```

---

## `ask` — Single Question, Full Wait

AI-generated answer grounded in real-time web search. Waits for complete response.

```bash
# Basic
perplexity-cli ask "What is quantum computing?"

# With model and reasoning
perplexity-cli ask "Compare React vs Vue in 2025" --model sonar-pro
perplexity-cli ask "Analyze this algorithm's complexity" --model sonar-reasoning --reasoning high

# Human-readable (remember: global flag before subcommand)
perplexity-cli --text ask "Latest Python features" --recency month

# System prompt
perplexity-cli ask "Summarize this topic" --system "Respond in 3 bullet points. Be concise."

# Get related questions and images
perplexity-cli ask "Best Python ORMs" --related --images

# JSON input
perplexity-cli ask --json '{"question": "What is Rust?", "model": "sonar-pro", "reasoning_effort": "high"}'

# Stdin
echo '{"question": "Explain async/await", "model": "sonar-pro"}' | perplexity-cli ask
```

### `ask` Options

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--model` | `-m` | string | `sonar` | Model to use (see Models table) |
| `--system` | `-s` | string | — | System prompt |
| `--mode` | | `web`\|`academic`\|`sec` | — | Search mode for grounding |
| `--recency` | `-r` | `hour`\|...\|`year` | — | Recency filter |
| `--domains` | `-d` | comma-separated | — | Domain filter |
| `--temperature` | `-t` | `0.0`–`2.0` | — | Randomness |
| `--max-tokens` | | int | — | Response length cap |
| `--reasoning` | | `minimal`\|`low`\|`medium`\|`high` | — | Reasoning effort |
| `--related` | | flag | off | Include related questions |
| `--images` | | flag | off | Include image URLs |
| `--json` | `-j` | JSON string | — | Full params as JSON |

### `ask` / `chat` JSON Input Schema

```json
{
  "question": "string (required)",
  "model": "sonar",
  "system_prompt": "optional system message",
  "search_mode": "web | academic | sec",
  "search_recency_filter": "hour | day | week | month | year",
  "search_domain_filter": ["domain.com"],
  "temperature": 0.2,
  "max_tokens": 1000,
  "reasoning_effort": "minimal | low | medium | high",
  "return_related_questions": false,
  "return_images": false
}
```

### `ask` / `chat` JSON Output Schema

```json
{
  "content": "The AI-generated answer text",
  "model": "sonar",
  "citations": ["https://source1.com", "https://source2.com"],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 180,
    "total_tokens": 222
  },
  "related_questions": ["Follow-up question 1?", "Follow-up question 2?"]
}
```

---

## `chat` — Streaming Response

Like `ask` but streams tokens as they arrive.

```bash
# Stream to terminal (text mode)
perplexity-cli --text chat "Explain quantum computing"

# Stream in JSON mode: chunks → stderr, final JSON → stdout
perplexity-cli chat "Latest AI news" --model sonar-pro

# Capture final JSON while watching progress
perplexity-cli chat "Explain monads" 2>/dev/null

# Disable streaming (equivalent to ask)
perplexity-cli chat "question" --no-stream
```

`chat` accepts the same options as `ask`, minus `--related` and `--images`.

---

## Models

| Model | Best for | Speed | Cost |
|-------|----------|-------|------|
| `sonar` | Quick factual Q&A (default) | Fast | Low |
| `sonar-pro` | Deep analysis, multi-step reasoning | Medium | Medium |
| `sonar-reasoning` | Complex analytical questions | Slow | High |
| `sonar-deep-research` | Extensive multi-round research | Slowest | Highest |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Auth error (bad/missing API key) or bad usage |
| `3` | Rate limit exceeded |
| `4` | Invalid input / validation error |
| `5+` | Server error (5xx from API) |
| `130` | Interrupted (Ctrl+C) |

---

## Agent Patterns

### Extract answer text only
```bash
perplexity-cli ask "What is TLS?" | jq -r '.content'
```

### Get citations as a list
```bash
perplexity-cli ask "Latest Node.js release" | jq '.citations[]'
```

### Pipe search results to jq
```bash
perplexity-cli search "python packaging" | jq '.results[] | {url, name}'
```

### Use JSON input for complex structured queries
```bash
perplexity-cli ask --json '{
  "question": "What changed in Python 3.13?",
  "model": "sonar-pro",
  "search_recency_filter": "year",
  "reasoning_effort": "high"
}'
```

### Stdin from another tool
```bash
echo '{"question": "Summarize this", "model": "sonar-pro"}' \
  | perplexity-cli ask \
  | jq -r '.content'
```

### Suppress streaming noise, capture JSON
```bash
result=$(perplexity-cli chat "Explain TLS" 2>/dev/null)
echo "$result" | jq -r '.content'
```

### Check for errors in scripts
```bash
if ! perplexity-cli ask "test" > /dev/null 2>&1; then
  echo "Perplexity API unavailable (exit $?)"
fi
```

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `perplexity-cli ask "q" --text` | `perplexity-cli --text ask "q"` |
| `perplexity-cli ask "q" --pretty` | `perplexity-cli --pretty ask "q"` |
| `perplexity-cli ask "q" --api-key KEY` | `perplexity-cli --api-key KEY ask "q"` |
| Parsing streamed stderr as JSON | Redirect `2>/dev/null` or use `ask` instead |
| Forgetting `query` key in JSON for search | `{"query": "..."}` is required |
| Forgetting `question` key in JSON for ask | `{"question": "..."}` is required |
| One monolithic question with 3+ "and" clauses | Split into rounds; reflect between rounds (see Research Methodology) |
| Hyper-specific opening question | Start broad ("what is the landscape of X?") then narrow based on what surfaced |
| Filtering search on `.snippet != null` | Returns `[]` on OpenRouter fallback path — `snippet` is always null there |
