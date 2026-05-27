---
id: PHI-002
title: Context quality is the highest-leverage improvement
date: 2026-05-28
status: stable
area: philosophy, review_engine, architecture
---

## Invariant

The highest-leverage improvement at any phase is context quality, not more
features. All real review quality gains come from giving the model better
structured knowledge of the system it is reasoning about — not from adding
more passes, more tools, or a larger model.

## Rationale

A model reviewing a file in isolation produces findings that are correct but
low-leverage — generic style notes, obvious missing docstrings. A model
reviewing a file with architecture role, cross-file dependencies, relevant ADRs,
and past findings produces findings that are structurally significant — boundary
violations, contract drift, real regressions. The difference is context, not
capability.

## How to maintain

- New context sources (callgraph, architecture memory, golden reviews) take
  priority over new AI passes.
- `ContextSelector` enforces a budget so context is curated, not dumped.
- Priority order: architecture decisions (1) > past findings (2) > cross-file
  context (3). The model should always know the invariants before it sees the details.
- When choosing between adding a new MCP tool and improving an existing context
  source, default to improving context.
