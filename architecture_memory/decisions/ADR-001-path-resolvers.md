---
id: ADR-001
title: Path resolvers are the only filesystem boundary mechanism
date: 2026-05-28
status: accepted
area: safety, server, paths
---

## Decision

All filesystem access from MCP tools must go through `resolve_repo_file` or
`resolve_allowed_local_file`. No tool may construct an absolute filesystem path
directly or accept a caller-supplied path without passing it through one of
these resolvers.

## Rationale

Without a centralized boundary, each tool author must independently reason about
path traversal, symlink escapes, and allowlist enforcement. One missed validation
anywhere in 61 tools exposes the entire filesystem. The resolvers are tested,
audited, and documented. Centralizing all access through them makes the safety
model auditable in one place.

## Consequences

- New tools that need filesystem access must use the correct resolver.
- Tools that only read the repo use `resolve_repo_file`.
- Tools that need external paths (Guitar Pro, images, open-in-app) use
  `resolve_allowed_local_file` with an explicit allowlist entry.
- Any tool that bypasses the resolvers is a Class C or D safety violation
  regardless of its declared class.
