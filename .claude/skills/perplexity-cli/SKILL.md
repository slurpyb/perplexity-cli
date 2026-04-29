---
name: perplexity-cli
description: >-
  Perplexity AI CLI tool reference for agents. Provides correct command
  syntax, flag ordering rules, JSON schemas, and agent patterns.
  TRIGGER when: user mentions "perplexity-cli", "perplexity cli",
  "perplexity search", "perplexity ask", "perplexity chat",
  or asks how to use, query, or invoke Perplexity from the command line.
  Also triggers when a user is writing a shell command or script that
  calls perplexity-cli and needs correct syntax.
origin: local
metadata:
  repo: perplexity-cli
  version: "1.0.0"
allowed-tools:
  - Read
  - Bash
---

# perplexity-cli

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

## Detailed References

Load these when you need full option tables, schemas, or patterns:

- **Full command syntax + all flags** → [references/commands.md](references/commands.md)
- **JSON input/output schemas** → [references/schemas.md](references/schemas.md)
- **Agent recipes + piping patterns** → [references/patterns.md](references/patterns.md)
- **Model selection guide** → [references/models.md](references/models.md)

---

## Setup

```bash
export PERPLEXITY_API_KEY="pplx-..."   # required; or pass --api-key globally
```

Exit codes: `0` success · `2` auth/usage error · `3` rate limit · `4` validation · `5+` server error
