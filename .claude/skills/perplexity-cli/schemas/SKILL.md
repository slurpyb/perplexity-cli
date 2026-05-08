---
name: perplexity-cli-schemas
description: JSON input and output schemas for all perplexity-cli commands (search, ask, chat). Use when constructing --json payloads or parsing command output programmatically.
---

# perplexity-cli — JSON Schemas

All commands accept `--json` or stdin JSON. All commands emit JSON by default.

---

## `search` — Input Schema

Passed via `--json 'JSON'` or piped via stdin.

```json
{
  "query": "string or array of strings (required)",
  "search_mode": "web | academic | sec",
  "search_recency_filter": "hour | day | week | month | year",
  "search_domain_filter": ["domain1.com", "domain2.com"],
  "search_language_filter": ["en", "fr"],
  "max_results": 10,
  "max_tokens": 500,
  "country": "US",
  "search_after_date_filter": "MM/DD/YYYY",
  "search_before_date_filter": "MM/DD/YYYY"
}
```

**Field notes:**
- `query` — the only required field; can be a string or list of strings
- `search_domain_filter` — array of domain strings, not a comma-separated string (unlike CLI `--domains`)
- `search_language_filter` — array of ISO 639-1 codes
- `search_after_date_filter` / `search_before_date_filter` — must use `MM/DD/YYYY` format
- All other fields optional; omit to use API defaults

**Minimal valid payload:**
```json
{"query": "Python 3.13 features"}
```

**Maximal payload:**
```json
{
  "query": "climate change research",
  "search_mode": "academic",
  "search_recency_filter": "year",
  "search_domain_filter": ["nature.com", "science.org"],
  "search_language_filter": ["en"],
  "max_results": 10,
  "max_tokens": 500,
  "country": "US",
  "search_after_date_filter": "01/01/2024",
  "search_before_date_filter": "12/31/2024"
}
```

---

## `search` — Output Schema

```json
{
  "query": "string or list of strings",
  "results": [
    {
      "url": "https://example.com/article",
      "name": "Article title (may be null)",
      "snippet": "Relevant excerpt from the page (may be null)",
      "date": "2024-03-15 (may be null)"
    }
  ]
}
```

**Accessing results with jq:**
```bash
# All URLs
perplexity-cli search "AI tools" | jq '.results[].url'

# Titles and URLs
perplexity-cli search "Rust frameworks" | jq '.results[] | {title: .name, url}'

# First result's snippet
perplexity-cli search "Python ORMs" | jq -r '.results[0].snippet'

# Count results
perplexity-cli search "ML papers" --mode academic | jq '.results | length'

# Filter to results with snippets
perplexity-cli search "WebAssembly" | jq '[.results[] | select(.snippet != null)]'
```

---

## `ask` — Input Schema

Passed via `--json 'JSON'` or piped via stdin.

```json
{
  "question": "string (required)",
  "model": "sonar | sonar-pro | sonar-reasoning | sonar-deep-research",
  "system_prompt": "optional system message string",
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

**Field notes:**
- `question` — required
- `model` — defaults to `sonar`; choose based on complexity (see [models/SKILL.md](../models/SKILL.md))
- `temperature` — float `0.0`–`2.0`; omit to use model default
- `reasoning_effort` — only meaningful for `sonar-reasoning` and `sonar-pro`
- `search_domain_filter` — array, not comma-separated string
- `return_related_questions` / `return_images` — boolean; only available in `ask`, not `chat`

**Minimal valid payload:**
```json
{"question": "What is quantum entanglement?"}
```

**Maximal payload:**
```json
{
  "question": "What are the security implications of JWT refresh token rotation?",
  "model": "sonar-pro",
  "system_prompt": "Be precise. Reference CVEs where relevant. Use bullet points.",
  "search_mode": "web",
  "search_recency_filter": "year",
  "search_domain_filter": ["portswigger.net", "owasp.org"],
  "temperature": 0.1,
  "max_tokens": 2000,
  "reasoning_effort": "high",
  "return_related_questions": true,
  "return_images": false
}
```

---

## `ask` / `chat` — Output Schema

```json
{
  "content": "The AI-generated answer as a string",
  "model": "sonar",
  "citations": [
    "https://source1.com/article",
    "https://source2.com/page"
  ],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 318,
    "total_tokens": 360
  },
  "related_questions": [
    "What is the difference between JWT and session tokens?",
    "How do you implement token rotation securely?"
  ]
}
```

**Field notes:**
- `content` — always a string; empty string if the API returned nothing
- `citations` — list of URLs the answer was grounded in; may be empty
- `usage` — always present; token counts may be 0 if not reported by the API
- `related_questions` — only populated when `--related` / `return_related_questions: true` was set
- `chat` output omits `related_questions` (not supported in streaming mode)

**Accessing output with jq:**
```bash
# Plain answer text
perplexity-cli ask "What is TLS?" | jq -r '.content'

# Citations as numbered list
perplexity-cli ask "Rust ownership" | jq -r '.citations | to_entries[] | "[\(.key+1)] \(.value)"'

# Token usage
perplexity-cli ask "Explain monads" | jq '.usage'

# Related questions
perplexity-cli ask "Python async?" --related | jq -r '.related_questions[]'

# Full structured response
perplexity-cli ask "Compare ORMs" --model sonar-pro | jq '{
  answer: .content,
  sources: .citations,
  tokens: .usage.total_tokens
}'
```

---

## CLI ↔ JSON Field Mapping

When both `--json` and CLI flags are provided, **CLI flags win**.

| CLI flag | JSON field |
|----------|-----------|
| `QUERY` (positional) | `query` |
| `QUESTION` (positional) | `question` |
| `--model` | `model` |
| `--system` | `system_prompt` |
| `--mode` | `search_mode` |
| `--recency` | `search_recency_filter` |
| `--domains` | `search_domain_filter` (CLI: comma string → JSON: array) |
| `--language` | `search_language_filter` (CLI: comma string → JSON: array) |
| `--temperature` | `temperature` |
| `--max-tokens` | `max_tokens` |
| `--reasoning` | `reasoning_effort` |
| `--related` | `return_related_questions` |
| `--images` | `return_images` |
| `--max-results` | `max_results` |
| `--country` | `country` |
| `--after` | `search_after_date_filter` |
| `--before` | `search_before_date_filter` |

**Gotcha:** `--domains github.com,stackoverflow.com` is a comma-separated string via CLI,
but `search_domain_filter` in JSON must be an **array**: `["github.com", "stackoverflow.com"]`.
