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
# 2  = auth error (bad/missing PERPLEXITY_API_KEY)
# 3  = rate limit
# 4  = validation error (bad JSON, bad field value)
# 5+ = server error
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
