# perplexity-cli

A CLI for the Perplexity AI API: web search, AI answers, streaming chat.

## Installation

pip install -e .

## Authentication

export PERPLEXITY_API_KEY="pplx-your-key"

Get your key at https://www.perplexity.ai/settings/api

## CRITICAL: Global flags before subcommand

CORRECT:   perplexity-cli --text ask "question"
INCORRECT: perplexity-cli ask "question" --text

--text, --pretty, --api-key must come BEFORE the subcommand.

## Quick Start

perplexity-cli search "Python 3.13 features"
perplexity-cli ask "What is quantum computing?"
perplexity-cli --text chat "Explain async/await"

## Output Formats

perplexity-cli ask "q"          # compact JSON (default, best for agents)
perplexity-cli --pretty ask "q" # indented JSON
perplexity-cli --text ask "q"   # plain text

## Commands

### search

Returns titles, URLs, snippets. No AI answer.

perplexity-cli search "climate research" --mode academic --recency year
perplexity-cli search "AAPL" --mode sec --max-results 5
perplexity-cli search --json '{"query": "AI news", "max_results": 5}'
echo '{"query": "AI news"}' | perplexity-cli search

Options: --mode (web/academic/sec), --recency (hour/day/week/month/year),
--domains, --language, --max-results, --country, --after, --before, --json

### ask

AI-generated answer grounded in web search. Waits for full response.

perplexity-cli ask "What is quantum computing?"
perplexity-cli ask "Compare React vs Vue" --model sonar-pro
perplexity-cli --text ask "Latest Python features" --recency month

Options: --model, --system, --mode, --recency, --domains,
--temperature, --max-tokens, --reasoning, --related, --images, --json

### chat

Like ask, but streams tokens in real time.

perplexity-cli --text chat "Explain monads"
perplexity-cli chat "AI news" --model sonar-pro
perplexity-cli chat "question" --no-stream  # same as ask

In JSON mode: streaming chunks to stderr, final JSON to stdout.

## Models

sonar               - Quick Q&A (default)
sonar-pro           - Deep analysis
sonar-reasoning     - Analytical questions
sonar-deep-research - Extensive research

## JSON Input / Stdin

perplexity-cli ask --json '{"question": "Rust vs Go?", "model": "sonar-pro"}'
echo '{"query": "...", "max_results": 3}' | perplexity-cli search

CLI flags override JSON values when both are provided.

## Scripting

perplexity-cli ask "What is TLS?" | jq -r .content
perplexity-cli ask "Python packaging" | jq .citations[]
result=$(perplexity-cli chat "Explain TLS" 2>/dev/null)

## Exit Codes

0   Success
2   Auth error / bad usage
3   Rate limit
4   Validation error
5+  Server error
130 Ctrl+C

## For AI Agents

See AGENTS.md for the full agent reference: schemas, correct flag ordering,
JSON patterns, and common mistakes.
