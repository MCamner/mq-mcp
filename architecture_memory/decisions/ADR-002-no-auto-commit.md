---
id: ADR-002
title: No MCP tool may commit or push to git automatically
date: 2026-05-28
status: accepted
area: safety, server, git
---

## Decision

No `@mcp.tool()` function may call `git commit` or `git push` (or equivalent)
automatically as a side effect of tool execution. Write-capable tools may write
files; committing and pushing remains an explicit human action.

## Rationale

Automatic commits in response to agent tool calls create unrecoverable shared
state without user confirmation. A single misconfigured agent run could pollute
remote history. The cost of requiring an explicit commit step is low; the cost
of an accidental force-push or secret leak to remote history is high.

## Consequences

- `update_repo_file` writes files but does not commit.
- The review engine writes to `review_engine/memory/` and `review_engine/context/`
  but does not commit those writes.
- Any future tool that needs to propose a commit must present the diff and
  require explicit user confirmation outside the tool call.
- `review_runtime_contract` checks server.py for git commit/push subprocess
  calls as a structural safety check.
