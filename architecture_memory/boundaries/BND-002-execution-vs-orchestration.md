---
id: BND-002
title: mq-agent orchestrates, mq-mcp executes — the boundary must not blur
date: 2026-05-28
status: accepted
area: boundaries, architecture, orchestration
---

## Boundary

mq-agent is the orchestration layer. It decides what to do, in what order,
and with what inputs. mq-mcp is the execution layer. It does exactly what a
tool call specifies — deterministically, with declared side effects.

mq-mcp tools must not:

- Make multi-step decisions about what to do next
- Call other MCP tools internally
- Maintain session state between tool calls
- Adapt behavior based on inferred orchestration intent

## Rationale

Blurring the boundary creates an implicit agent inside a tool, which breaks
the determinism guarantee and makes behavior unpredictable. If a tool starts
deciding "what should I do next", it has become an orchestrator — and mq-agent
can no longer reason about what the tool will do.

## Consequences

- `review_repo` iterates over files but each file review is an independent
  tool call — no state flows between iterations inside the tool.
- Tools return structured output; mq-agent decides what to do with it.
- v1.3.0 will formalize this in `docs/ORCHESTRATION_CONTRACT.md`.
