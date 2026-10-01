---
name: feedback-review
description: Use when inspecting MQ Feedback Engine evidence, explaining comparisons or candidates, or deciding which read-only feedback tool to call without changing policy.
---

# Feedback Review

Use this skill to inspect and explain mq-agent Feedback Engine evidence through
mq-mcp. The skill chooses tools; it does not contain verdict, promotion, or
activation policy.

## When to use

- Inspect Feedback Engine health or recent experiment state.
- Explain one feedback experiment and its stored comparison.
- Read the latest deterministic comparison and per-metric deltas.
- List reviewable improvement candidates.
- Start an explicitly requested bounded feedback experiment.

## When not to use

- Do not derive a new verdict from model preference.
- Do not approve, reject, purge, hand off, or activate a candidate.
- Do not write directly to the feedback store.
- Do not replace mq-agent comparison logic with prompt instructions.

## Tool routing

- Health/coverage → \`mq_feedback_status\`
- One experiment chain → \`mq_feedback_inspect\`
- Latest stored comparison → \`mq_feedback_compare\`
- Aggregate evidence → \`mq_feedback_report\`
- Candidate list → \`mq_feedback_candidates\`
- Explicit bounded experiment → \`mq_feedback_run\`

The first five are read-only. \`mq_feedback_run\` records local runtime evidence,
so it remains separately safety-classified and must not be treated as a
read-only lookup.

## Ownership

- mq-agent owns experiment collection, comparison contracts, verdicts and
  candidates.
- mq-mcp owns only the MCP adapter in \`mq-mcp/feedback_bridge.py\` and the tool
  registrations in \`mq-mcp/server.py\`.
- mqobsidian owns durable memory scoring/review/promotion.
- Clients such as Codex and Claude consume the same MCP tools and must see the
  same underlying evidence.

## Evals

### Should trigger

- "show the latest MQ feedback comparison"
- "why is this feedback candidate proposed?"
- "check feedback status through MCP"
- "run a bounded repo-review feedback experiment"

### Should not trigger

- "activate the winning feedback policy"
- "promote this directly into durable memory"
- "rewrite the feedback verdict"
- "delete all feedback evidence"
