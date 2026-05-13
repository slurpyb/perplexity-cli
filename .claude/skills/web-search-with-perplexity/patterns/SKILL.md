---
name: perplexity-cli-patterns
description: Agent recipes, piping patterns, scripting idioms, and common workflows for perplexity-cli. Use when constructing multi-step queries, piping output, or integrating into agent workflows.
---

# perplexity-cli — Agent Patterns

Practical recipes for integrating `perplexity-cli` into agent workflows and scripts.

---

## Extracting Output with jq

```bash
# Answer text only (most common agent use)
perplexity-cli ask "What is TLS?" | jq -r '.content'

# All citation URLs, one per line
perplexity-cli ask "Rust ownership" | jq -r '.citations[]'

# Numbered citations
perplexity-cli ask "Python ORMs" | jq -r '.citations | to_entries[] | "[\(.key+1)] \(.value)"'

# Search: titles + URLs
perplexity-cli search "AI frameworks" | jq '.results[] | "\(.name): \(.url)"'

# Search: only results that have snippets
# NOTE: returns [] on the OpenRouter fallback path (no snippet exposed there)
perplexity-cli search "async Rust" | jq '[.results[] | select(.snippet != null)]'

# Token cost of a query
perplexity-cli ask "Explain OAuth2" | jq '.usage.total_tokens'

# Full structured summary
perplexity-cli ask "Compare Postgres vs MySQL" --model sonar-pro | jq '{
  answer: .content,
  sources: (.citations | length),
  tokens: .usage.total_tokens
}'
```

---

## Stdin Pipe Patterns

Stdin accepts the same JSON format as `--json`. Useful when building queries in code.

```bash
# Build query in Python, pipe to CLI
python3 -c "
import json, sys
q = {'question': 'What is WebAssembly?', 'model': 'sonar-pro'}
sys.stdout.write(json.dumps(q))
" | perplexity-cli ask | jq -r '.content'

# Compose multi-field search in shell
printf '{"query": "Rust async", "search_domain_filter": ["doc.rust-lang.org"], "max_results": 5}' \
  | perplexity-cli search \
  | jq '.results[].url'

# Read query from a file
cat query.json | perplexity-cli ask | jq -r '.content'
```

---

## Capturing Streaming Output (chat)

In JSON mode, `chat` sends streaming chunks to **stderr** and final JSON to **stdout**.
This makes it easy to discard progress noise and capture clean output.

```bash
# Discard streaming chunks, capture final JSON
result=$(perplexity-cli chat "Explain TLS handshake" 2>/dev/null)
echo "$result" | jq -r '.content'

# Redirect streaming progress to a log, capture JSON
perplexity-cli chat "Rust borrow checker" 2>>streaming.log | jq '.citations[]'

# Use --no-stream to avoid the stderr/stdout split entirely
perplexity-cli chat "What is async/await?" --no-stream | jq -r '.content'
```

---

## Research Methodology — Read This First

**Prefer many small queries over one monolithic question.** Big composite queries collapse into shallow surface-level answers. Several focused queries — followed by reflection on the answers, then a new round of follow-ups — produce dramatically better synthesis.

**Start broad, circle in.** Hyper-specific opening questions double down on whatever bias is in the prompt. The model anchors to your phrasing instead of the actual landscape. Open wide, see what comes back, then narrow to the real questions surfaced by the first round.

### Anti-pattern (one big monolithic ask)

```bash
# ❌ Lazy: one giant question, single shallow answer, no chance to course-correct
perplexity-cli ask "Compare PostgreSQL vs MySQL vs SQLite vs CockroachDB vs DynamoDB \
  for a multi-region SaaS with strong consistency, 10M users, sub-100ms p99 latency, \
  and tell me which one to pick and why" --model sonar-pro
```

### Pattern (broad → reflect → narrow)

```bash
#!/usr/bin/env bash
# Round 1: broad landscape — what are the real options?
perplexity-cli ask "What database architectures do multi-region SaaS products use in 2026?" \
  --model sonar-pro \
  | jq -r '.content' > /tmp/r1.txt

# AGENT REFLECTS on /tmp/r1.txt:
#   - which architectures showed up?
#   - which constraints actually drive the choice?
#   - what assumptions in the original prompt were wrong?

# Round 2: narrow on the real axes surfaced by round 1
perplexity-cli ask "How do products handle write conflicts under multi-region active-active Postgres?" \
  --model sonar-pro --recency year | jq -r '.content' > /tmp/r2a.txt

perplexity-cli ask "What latency penalty does CockroachDB serializable isolation add at 10M user scale?" \
  --model sonar-pro --recency year | jq -r '.content' > /tmp/r2b.txt

# AGENT REFLECTS again. Round 3 = decide what's missing, fill the gap.
perplexity-cli ask "Which of these tradeoffs change when sub-100ms p99 is a hard constraint?" \
  --model sonar-pro | jq -r '.content' > /tmp/r3.txt
```

### Rules of thumb

| Situation | What to do |
|---|---|
| Topic is unfamiliar | Round 1 must be **deliberately vague**. "What do people use for X?" beats "Should I use Foo or Bar for X?" |
| You think you already know the answer | Bias check — phrase Round 1 as if you're learning the topic for the first time |
| One question has 3+ "and" clauses | Split it. Each clause becomes its own ask. |
| Two queries return overlapping content | You're not narrowing enough — make Round 2 sharper based on Round 1 specifics |
| Answer feels generic | Take a concrete noun/term from the response and ask a follow-up centered on it |

### Reflect-loop template

```bash
TOPIC="$1"

# Broad opener — no opinions baked in
R1=$(perplexity-cli ask "What is the current landscape of $TOPIC?" --model sonar-pro | jq -r '.content')

# Pull 2-3 specific terms or options the answer surfaced.
# (Agent does this — don't pre-assume what they'll be.)
TERMS=$(echo "$R1" | extract_specific_terms.sh)   # your extraction step

# Round 2: one focused ask per surfaced term
for term in $TERMS; do
  perplexity-cli ask "What are the failure modes / tradeoffs of $term in $TOPIC?" \
    --model sonar-pro --recency year \
    | jq -r '.content' > "/tmp/r2-$term.txt"
done

# Round 3: synthesis question that references what you actually learned
perplexity-cli ask "Given <specific findings from r2>, which approach fits <real constraint>?" \
  --model sonar-pro
```

---

## Multi-Step Research Workflow

```bash
#!/usr/bin/env bash
# Research a topic: search first, then ask for synthesis

TOPIC="Rust vs Go for web services 2025"

# Step 1: get raw sources
SOURCES=$(perplexity-cli search "$TOPIC" --recency year --max-results 10)
echo "$SOURCES" | jq -r '.results[].url'

# Step 2: synthesize with sonar-pro, grounded in recent web sources
ANSWER=$(perplexity-cli ask "$TOPIC" \
  --model sonar-pro \
  --recency year \
  | jq -r '.content')

echo "=== Answer ===" 
echo "$ANSWER"
```

---

## Conditional on Exit Code

```bash
# Only proceed if query succeeds
if perplexity-cli ask "test connectivity" > /dev/null 2>&1; then
  echo "API reachable"
else
  echo "API error (exit $?)"
  exit 1
fi

# Exit code map:
# 0  = success
# 2  = auth error (no usable PERPLEXITY_API_KEY or OPENROUTER_API_KEY)
# 3  = rate limit (after fallback also exhausted)
# 4  = validation error (bad JSON, bad field value)
# 5+ = server error (after fallback also exhausted)
```

---

## Domain-Scoped Research

```bash
# Official docs only
perplexity-cli ask "Python asyncio best practices" \
  --domains "docs.python.org" \
  --recency year \
  | jq -r '.content'

# Rust: official + community blogs
perplexity-cli ask "Rust 2024 edition changes" \
  --domains "blog.rust-lang.org,doc.rust-lang.org" \
  | jq '{answer: .content, sources: .citations}'

# Security: OWASP + PortSwigger only
perplexity-cli ask "SSRF prevention techniques" \
  --domains "owasp.org,portswigger.net" \
  --model sonar-pro \
  | jq -r '.content'
```

---

## Academic & Financial Research

```bash
# Peer-reviewed sources only
perplexity-cli search "LLM reasoning capabilities 2024" \
  --mode academic \
  --recency year \
  | jq '.results[] | {title: .name, url}'

# Ask with academic grounding
perplexity-cli ask "What does recent research say about RAG limitations?" \
  --mode academic \
  --recency year \
  --model sonar-pro \
  | jq -r '.content'

# SEC filings
perplexity-cli search "Apple revenue Q2 2025" --mode sec | jq '.results[].url'
```

---

## System Prompt Patterns

```bash
# Force structured JSON output in the answer
perplexity-cli ask "Top Python web frameworks" \
  --system 'Respond ONLY with a JSON array. Each item: {"name": "...", "stars": "...", "best_for": "..."}. No prose.' \
  | jq -r '.content' \
  | python3 -m json.tool

# Enforce terse bullet-point responses
perplexity-cli ask "Rust vs Go tradeoffs" \
  --system "Respond in exactly 5 bullet points. Each bullet max 15 words." \
  | jq -r '.content'

# Role + domain constraints
perplexity-cli ask "Explain the CAP theorem" \
  --system "You are a distributed systems professor. Use concrete real-world examples." \
  --model sonar-pro \
  | jq -r '.content'
```

---

## Using --json for Reproducible Agent Invocations

JSON input is the most reliable form for agents because it avoids shell quoting issues
and makes parameters explicit and inspectable.

```bash
# Store query as JSON, run it
QUERY='{
  "question": "What is the current state of WebGPU browser support?",
  "model": "sonar-pro",
  "search_recency_filter": "month",
  "reasoning_effort": "medium"
}'

echo "$QUERY" | perplexity-cli ask | jq -r '.content'

# Use Python to build the payload cleanly
python3 -c "
import json
payload = {
    'question': 'Compare Tokio vs async-std',
    'model': 'sonar-pro',
    'search_domain_filter': ['tokio.rs', 'docs.rs'],
    'reasoning_effort': 'high'
}
print(json.dumps(payload))
" | perplexity-cli ask | jq -r '.content'
```

---

## Common Mistakes and Fixes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| `perplexity-cli ask "q" --text` | `--text` silently ignored; outputs JSON | `perplexity-cli --text ask "q"` |
| `perplexity-cli ask "q" --pretty` | `--pretty` silently ignored; outputs compact JSON | `perplexity-cli --pretty ask "q"` |
| `perplexity-cli ask "q" --api-key KEY` | `--api-key` ignored; uses env var or fails | `perplexity-cli --api-key KEY ask "q"` |
| Parsing `chat` stdout as streaming | Streaming chunks (not JSON) hit stdout in `--text` mode | Use JSON mode (default) + `2>/dev/null` |
| `--domains` as array in JSON field | Field expects array, not comma string | `"search_domain_filter": ["a.com", "b.com"]` |
| Missing `query` key in search JSON | Validation error (exit 4) | `{"query": "..."}` is required |
| Missing `question` key in ask JSON | Validation error (exit 4) | `{"question": "..."}` is required |
| `--recency` without quotes | Shell word splitting if value is a variable | Always quote: `--recency "month"` |
