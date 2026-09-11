---
id: BND-003
title: Bridget stores context, not knowledge
date: 2026-09-10
status: accepted
area: boundaries, bridget, memory, orchestration, codegraph
---

## Boundary

Bridget may keep bounded local session context so an operator can continue a
conversation, inspect recent work, and reuse nearby repo context.

Bridget must not:

- Treat conversation history as evidence
- Promote session logs into learning records by itself
- Write to mqobsidian as a knowledge producer
- Turn CodeGraph output into `memory-observation.v1`
- Hold workflow state, retry policy, or tool-selection policy

## Ownership

- Bridget stores temporary context.
- mqobsidian stores durable knowledge.
- mq-agent plans and orchestrates work.
- CodeGraph provides structural context.
- mq-mcp owns deterministic tools, safety metadata, review, and validation.

## Consequences

- `bridget --learn-last` may preview a candidate, but storage still requires an
  approved learn tool or mqobsidian flow.
- `bridget --history` and `bridget --forget` operate only on Bridget session
  context.
- CodeGraph lookup commands are read-only context commands.
- Session logs never count as validation evidence for a learning record.
