---
id: ADR-007
title: Context, knowledge, orchestration, and source intelligence remain separate
date: 2026-08-13
status: accepted
area: bridget, context, mq-agent, mqobsidian, codegraph, mqlaunch, boundaries
---

## Decision

The MQ stack keeps four responsibilities separate:

```text
Bridget    stores bounded, temporary conversation context
mqobsidian stores reviewed, durable knowledge and versioned truth surfaces
mq-agent   plans, routes, delegates, and coordinates multi-step work
CodeGraph  provides repo-local structural source intelligence
```

mq-mcp remains the deterministic execution and safety-contract owner underneath
Bridget. mqlaunch remains a thin human/operator entrypoint that may invoke or
display these capabilities but does not become a competing context, knowledge,
or orchestration layer.

The boundaries are mandatory:

- Bridget session history is context, not evidence. It may suggest a learning
  candidate but may not autonomously store or promote durable knowledge.
- mqobsidian owns durable reviewed knowledge, schemas, context contracts, and
  materialized truth manifests. It is not live runtime truth and executes no
  workflows or tools.
- mq-agent selects workflows, repositories, models, and delegation. It consumes
  mq-mcp contracts and must not duplicate execution or review logic.
- CodeGraph answers structural questions about current indexed source. Its
  daemon owns `.codegraph/codegraph.db`; MQ components use supported CLI/MCP
  interfaces and never read, edit, or delete the database directly.
- Claude Code and Codex use their installed CodeGraph MCP integration directly;
  supported CodeGraph CLI commands are the terminal-only fallback. Installation,
  agent wiring, and tool selection are documented by mqobsidian in
  `docs/integrations/codegraph.md`.
- CodeGraph output may guide exploration and suggest candidates, but graph data
  is not observation evidence and may not promote memory by itself.
- mqlaunch may surface status and commands, but authoritative state remains in
  the owning runtime, repository, or versioned mqobsidian truth manifest.

## Rationale

Combining these roles creates competing truth planes and implicit agents. A
conversation log treated as knowledge can silently become permanent. A vault
treated as live runtime truth becomes stale. An execution tool that plans its
next action becomes an orchestrator. A graph database treated as evidence can
promote high-volume structure without proving that a lesson helped real work.

Keeping the layers separate makes side effects, provenance, freshness, and
approval gates auditable. It also allows each component to evolve without
copying another repository's contracts.

## Consequences

- Bridget context must stay bounded, temporary, redactable, and independently
  deletable. Durable writes require an explicit Class C tool and approval.
- mqobsidian context may orient work, but current behavior must be verified in
  source, tests, CLI output, or runtime contracts before action.
- mq-agent owns multi-step choice and delegation; mq-mcp tools remain bounded
  and deterministic.
- CodeGraph failures degrade to targeted source inspection. Index repair uses
  `codegraph status`, `codegraph sync`, or `codegraph unlock`, never direct
  SQLite access.
- mqlaunch remains a presentation and entrypoint layer; it must not reconstruct
  durable knowledge or source intelligence.
- Any cross-layer integration must preserve provenance and state whether its
  input is context, runtime truth, durable knowledge, or evidence.

## Related documentation

- `mqobsidian/docs/integrations/codegraph.md`
- `mqobsidian/decisions/ADR-009-codegraph-memory-boundary.md`
