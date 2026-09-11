# Bridget / mq-agent Boundary

Bridget is the local execution assistant. It is good for short, local,
operator-driven work: one-shot prompts, interactive chat, repo context,
read-only CodeGraph lookups, and explicit tool calls through mq-mcp.

mq-agent is the planner and orchestrator. Use it for multi-step workflows,
cross-repo plans, long-running work, retry policy, routing policy, or anything
that needs workflow state.

## Rule

```text
Bridget executes nearby work.
mq-agent plans coordinated work.
```

Bridget may suggest delegation when a request looks multi-step, cross-repo, or
long-running. It must not start orchestration unless the operator asks for
`--workflow` or explicitly approves the handoff.

## Memory

Bridget session history is temporary context. It is not evidence, not durable
knowledge, and not approval to store a learning.

`bridget --learn-last` only previews a redacted learning candidate. A separate
approved learn or mqobsidian flow owns storage and promotion.
