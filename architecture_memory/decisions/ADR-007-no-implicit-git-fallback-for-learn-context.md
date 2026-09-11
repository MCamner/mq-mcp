---
id: ADR-007
title: Learn extraction does not silently fall back from repo-signal to git
date: 2026-09-11
status: accepted
area: learning, evidence, safety, repo-context
---

## Decision

Repository-specific learn extraction must not silently replace unavailable
repo-signal evidence with a git subprocess.

The primary evidence source remains the verified
`.repo-signal/exports/symbol_index.json` contract. If that artifact is missing
or stale, the current behavior remains a deterministic low-confidence refusal
with empty evidence.

A future git fallback may be introduced only as an explicit contract change
that makes the source visible to the operator and updates the tool's declared
safety behavior before the subprocess can run.

## Rationale

The idea was evaluated after repo-context freshness was enforced in #67.
A read-only `git ls-files` fallback would improve availability, but it would
change more than the evidence source:

- `ollama_learn_extract` and `learn_extract_from_last_review` are currently
  Class B surfaces whose documentation says they do not execute commands.
- ADR-003 classifies subprocess tools as Class D and requires subprocess
  confirmation.
- The current human-readable previews do not expose which repo-context source
  was used, so an automatic fallback would be invisible at the operator
  boundary.
- Treating missing evidence as refusal is safer than silently widening both the
  trust source and execution surface.

The fallback is therefore not rejected forever; it is rejected as an implicit
behavior under the current contract.

## Preconditions for reconsidering

A git fallback can be reconsidered only when all of these move together:

1. Human-readable learn previews show the context source and provenance.
2. Tool safety metadata, docstrings, and contracts explicitly declare the git
   subprocess behavior and the correct safety class/approval semantics.
3. The fallback is deterministic and repo-scoped: fixed argv, no shell,
   bounded timeout, tracked files only, path-containment checks, and no writes.
4. Tests prove repo-signal remains preferred and that malformed, cross-repo, or
   future-dated evidence fails closed rather than being hidden by fallback.

## Consequences

- Missing or stale repo-signal context continues to refuse extraction rather
  than execute git automatically.
- Evidence-source changes cannot happen invisibly behind a stable MCP surface.
- The next bounded improvement remains human-readable provenance; subprocess
  fallback is downstream of that visibility and safety work.
