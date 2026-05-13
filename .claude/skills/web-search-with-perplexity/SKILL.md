---
name: web-search-with-perplexity
description: >-
  Web search via Perplexity AI CLI (perplexity-cli). Use for any web
  research, fact-finding, "look this up", "search the web", or
  AI-grounded answer with citations. Three commands: search (raw URLs),
  ask (AI answer + citations), chat (streaming AI answer). Supports
  PERPLEXITY_API_KEY primary backend with OPENROUTER_API_KEY fallback.
origin: local
metadata:
  repo: perplexity-cli
  version: "1.1.0"
allowed-tools:
  - Read
  - Bash
---

# web-search-with-perplexity

CLI wrapper for the Perplexity AI API. Three commands: `search`, `ask`, `chat`.

---

## ⚠️ #1 Agent Mistake — Global Flags Come BEFORE the Subcommand

```bash
# ✅ CORRECT
perplexity-cli --text ask "What is Rust?"
perplexity-cli --pretty search "AI news"
perplexity-cli --api-key sk-xxx ask "question"

# ❌ WRONG — typer silently ignores trailing global flags
perplexity-cli ask "What is Rust?" --text
perplexity-cli search "AI news" --pretty
```

`--text`, `--pretty`, and `--api-key` belong to the **root command**, not the
subcommand. They must precede `search`, `ask`, or `chat`.

---

## Commands at a Glance

| Command  | Purpose                              | Streams | Default output |
|----------|--------------------------------------|---------|----------------|
| `search` | Raw URLs + snippets, no AI answer    | No      | Compact JSON   |
| `ask`    | AI answer + citations, full wait     | No      | Compact JSON   |
| `chat`   | AI answer, tokens stream in real time| Yes     | JSON/text      |

**Default is compact JSON** — best for agents piping to `jq`.

---

## Output Format Flags (global — must precede subcommand)

| Flag       | Output                                     | Best for           |
|------------|--------------------------------------------|--------------------|
| *(none)*   | Compact JSON on stdout                     | Agents, `jq` pipes |
| `--pretty` | Indented JSON on stdout                    | Human inspection   |
| `--text`   | Plain text; `chat` streams tokens to stdout| Interactive use    |

---

## Quick Examples

```bash
# Search
perplexity-cli search "Python 3.13 features"
perplexity-cli --text search "best Python ORMs"

# Ask (non-streaming)
perplexity-cli ask "What is quantum computing?"
perplexity-cli --text ask "Latest Rust release" --recency month
perplexity-cli ask "Compare React vs Vue" --model sonar-pro

# Chat (streaming)
perplexity-cli --text chat "Explain monads"
perplexity-cli chat "AI news" --model sonar-pro 2>/dev/null  # final JSON only

# jq extraction
perplexity-cli ask "What is TLS?" | jq -r '.content'
perplexity-cli ask "Python packaging" | jq '.citations[]'
```

---

## Research Methodology — Read Before Composing Queries

**Many small queries beat one monolithic ask.** A composite "compare A vs B vs C and tell me which" produces shallow surface-level output. Several focused queries — followed by reflection on the answers, then a new round of follow-ups — produce dramatically better synthesis.

**Start broad, circle in.** Hyper-specific opening questions anchor the model to your prompt's bias instead of the actual landscape. Open wide, see what comes back, then narrow to the real questions surfaced by Round 1.

Pattern: `broad ask → reflect on answer → narrower asks on what surfaced → reflect → synthesis ask`. Full templates and rules of thumb in [patterns/SKILL.md](patterns/SKILL.md#research-methodology--read-this-first).

---

## Detailed References

Load these when you need full option tables, schemas, or patterns:

- **Full command syntax + all flags** → [commands/SKILL.md](commands/SKILL.md)
- **JSON input/output schemas** → [schemas/SKILL.md](schemas/SKILL.md)
- **Agent recipes + piping patterns** → [patterns/SKILL.md](patterns/SKILL.md)
- **Model selection guide** → [models/SKILL.md](models/SKILL.md)

---

## Setup

At least one of these must be set:

```bash
export PERPLEXITY_API_KEY="pplx-..."        # primary backend; or pass --api-key globally
export OPENROUTER_API_KEY="sk-or-v1-..."    # fallback backend (also works standalone)
```

**Backend resolution:**

| Keys present | Behavior |
|---|---|
| `PERPLEXITY_API_KEY` only | Native Perplexity API |
| `OPENROUTER_API_KEY` only | OpenRouter (routes to `perplexity/sonar*` models) |
| Both | Perplexity primary; falls back to OpenRouter on auth/quota/server/network errors (`401/402/403/408/429/5xx` + connection failures) |
| Neither | Exits `2` with a help message |

`--api-key` only sets the Perplexity key. OpenRouter key is env-only.

**Fallback caveats:**
- `search` on the OpenRouter path emulates via `perplexity/sonar-pro` chat. Returns `url` + `name` (title), but `snippet` is always `null` — OpenRouter doesn't expose snippet text.
- `chat` streaming fallback only triggers **before** the first chunk emits. Mid-stream errors propagate (no restart, would duplicate stdout).
- JSON output schema unchanged regardless of backend.

Exit codes: `0` success · `2` auth/usage error · `3` rate limit · `4` validation · `5+` server error
