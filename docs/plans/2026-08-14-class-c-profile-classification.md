# Class C Profile Classification Fix Implementation Plan

## Goal

Explicitly classify six approval-gated curation and mqobsidian write tools as
intentionally profile-free so orchestration validation has no false warning.

## Owner repo

mq-mcp

## Secondary repos

None.

## Architecture boundary

- mqobsidian owns context contracts, templates, generators, and published context surfaces.
- mq-agent owns planning, workflow routing, task decomposition, and agent handoff.
- mq-mcp owns execution tools, tool safety, and runtime boundaries.
- mq-hal owns status, operator summaries, release/runbook views.
- repo-signal owns publish readiness, security/readiness scoring, and repo health checks.

## Non-goals

- Do not add write-capable tools to default profiles.
- Do not change tool behavior, safety classes, or approval gates.

## Approval gates

- Before file writes: approved by the user's request.
- Before commit: separate user request required.
- Before push/merge: separate user request required.
- Before deletion/settings changes: separate approval required; none planned.

## Test gates

- `uv --directory mq-mcp run pytest ../tests/test_orchestration_contract_staleness.py -q --tb=short`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert this change; no runtime data or profile configuration is migrated.

### Task 1: Lock the intended classification

**Purpose:** Prevent new or existing manual Class C tools from producing an
unreviewed profile-coverage warning.

**Files:**

- Modify: `tests/test_orchestration_contract_staleness.py`
- Modify: `mq-mcp/server.py`

**Steps:**

1. Add a failing regression test for the current warning.
2. Add the six reviewed tools to the explicit profile-free set.
3. Clarify why curation and durable-memory writes remain opt-in.
4. Run focused and full validation.

**Expected result:** Orchestration validation reports Class C coverage as PASS
with zero warnings.

**Commit suggestion:**

`fix(profiles): classify manual Class C tools`
