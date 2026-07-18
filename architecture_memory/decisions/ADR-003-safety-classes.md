---
id: ADR-003
title: Every tool has a declared safety class A-D
date: 2026-05-28
status: accepted
area: safety, server, tools
---

## Decision

Every `@mcp.tool()` is assigned exactly one safety class from the set {A, B, C, D}.
The class is documented in `docs/TOOL_SAFETY.md` and `docs/tool_contracts.json`.
No tool may be added without a declared class.

Classes:

- A — read-only, repo-scoped
- B — read-only, allowed external paths or system reads
- C — write-capable, controlled scope
- D — subprocess / open-app

## Rationale

Without explicit classification, consumers (mq-agent, MCP clients) cannot make
informed trust decisions about tool calls. The four-class model maps directly
to the approval gates an agent or user must configure: A/B are safe to auto-approve,
C requires write confirmation, D requires subprocess confirmation.

## Consequences

- New tools must be classified before merge.
- `mcp-tool-safety-reviewer` agent validates classification on every server.py change.
- `detect_architecture_drift` checks that all tools in server.py appear in
  TOOL_SAFETY.md with a valid class.
- Class D tools may only invoke a fixed, declared subprocess command — not a
  dynamically constructed command.
