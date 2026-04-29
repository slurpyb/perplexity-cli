---
name: perplexity-cli-models
description: Model selection guide for perplexity-cli ask and chat commands. Use when choosing between sonar, sonar-pro, sonar-reasoning, and sonar-deep-research.
---

# perplexity-cli — Model Selection

The `--model` flag (or `"model"` in JSON input) controls which Sonar model handles your question.
Applies to `ask` and `chat`. Default is `sonar`.

---

## Model Comparison

| Model | Speed | Cost | Best for |
|-------|-------|------|----------|
| `sonar` | Fastest | Lowest | Quick factual questions, high-volume agent queries |
| `sonar-pro` | Medium | Medium | Deep analysis, comparisons, multi-part questions |
| `sonar-reasoning` | Slow | High | Complex analytical or logical questions |
| `sonar-deep-research` | Slowest | Highest | Extensive research with multiple search rounds |

---

## When to Use Each

### `sonar` (default)
Use for:
- Simple factual lookups: "What is the current version of Node.js?"
- High-volume batch queries where cost matters
- Quick context-gathering before a more complex follow-up
- Any question where speed > depth

```bash
perplexity-cli ask "What is the latest LTS version of Node.js?"
perplexity-cli ask "What does HTTP 429 mean?"
perplexity-cli search "Python 3.13 release date"
```

### `sonar-pro`
Use for:
- Comparative analysis: "Compare X vs Y"
- Multi-step reasoning where you want more than a surface answer
- Technical architecture questions
- Summaries of complex topics with citations
- When you want higher quality without the latency of reasoning models

```bash
perplexity-cli ask "Compare PostgreSQL vs CockroachDB for a multi-region SaaS" --model sonar-pro
perplexity-cli ask "What are the tradeoffs of event sourcing vs CQRS?" --model sonar-pro
perplexity-cli ask "Summarize recent changes in Kubernetes 1.30" --model sonar-pro --recency month
```

### `sonar-reasoning`
Use for:
- Questions that require logical deduction
- Algorithm complexity analysis
- Debugging assistance for tricky problems
- Math or formal reasoning
- Combine with `--reasoning high` for best results

```bash
perplexity-cli ask "What is the time complexity of Dijkstra's algorithm and why?" \
  --model sonar-reasoning --reasoning high

perplexity-cli ask "Given a distributed system with eventual consistency, explain why this race condition occurs: ..." \
  --model sonar-reasoning --reasoning high
```

### `sonar-deep-research`
Use for:
- Comprehensive literature reviews
- Research reports that need to synthesize many sources
- Questions where coverage > speed
- Generating reference material rather than quick answers
- Long wait times are acceptable

```bash
perplexity-cli ask "What does the current research literature say about transformer attention mechanisms and their computational limits?" \
  --model sonar-deep-research --mode academic

perplexity-cli ask "Provide a comprehensive overview of WebAssembly ecosystem tools as of 2025" \
  --model sonar-deep-research
```

---

## Reasoning Effort (`--reasoning`)

Only meaningful with `sonar-reasoning` and `sonar-pro`. Ignored by other models.

| Value | Use when |
|-------|----------|
| `minimal` | Speed is critical; shallow reasoning is fine |
| `low` | Slightly better than default; marginal cost increase |
| `medium` | Balanced — good default for `sonar-reasoning` |
| `high` | Complex questions where correctness matters more than speed |

```bash
# Quick estimation
perplexity-cli ask "Rough complexity of merge sort?" --model sonar-reasoning --reasoning minimal

# Deep analysis
perplexity-cli ask "Analyze the correctness of this distributed locking algorithm: ..." \
  --model sonar-reasoning --reasoning high
```

---

## Decision Flowchart

```
Is it a simple factual question?
  → YES: sonar (fast, cheap)
  → NO:
    Does it need logical/mathematical reasoning?
      → YES: sonar-reasoning + --reasoning high
      → NO:
        Does it need comprehensive coverage from many sources?
          → YES: sonar-deep-research
          → NO: sonar-pro (deep analysis, balanced speed/cost)
```

---

## Cost-Aware Agent Usage

For agents making many queries in a loop:

```bash
# Use sonar for bulk/filter queries
for topic in "Python" "Rust" "Go" "TypeScript"; do
  perplexity-cli ask "Latest stable version of $topic?" | jq -r '.content'
done

# Upgrade to sonar-pro only for the synthesis step
perplexity-cli ask "Given these versions, which language has the most active recent development?" \
  --model sonar-pro \
  --system "Be brief. One paragraph max."
```
