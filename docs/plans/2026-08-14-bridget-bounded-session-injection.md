# Bridget Bounded Session Injection Implementation Plan

## Goal

Bound Bridget's prompt injection to three sessions, 500 characters per session, and sessions no older than seven days.

## Owner repo

mq-mcp

## Secondary repos

none

## Architecture boundary

- mqobsidian owns context contracts, templates, generators, and published context surfaces.
- mq-agent owns planning, workflow routing, task decomposition, and agent handoff.
- mq-mcp owns execution tools, tool safety, and runtime boundaries.
- mq-hal owns status, operator summaries, release/runbook views.
- repo-signal owns publish readiness, security/readiness scoring, and repo health checks.

## Non-goals

- Changing stored session detail or retention.
- Promoting sessions to durable learning or evidence.

## Approval gates

- Before file writes: approved by the user's roadmap instruction
- Before commit: yes
- Before push/merge: yes
- Before deletion/settings changes: yes

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridget_runtime.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the bounded `load()` implementation, its tests, and the roadmap checkbox as one change.

### Task 1: Specify bounded injection

**Purpose:** Lock the count, size, and age limits with deterministic tests.

**Files:**

- Modify: `tests/test_bridget_context.py`

**Steps:**

1. Add history fixtures with fixed timestamps.
2. Assert newest-three selection, seven-day filtering, and 500-character blocks.
3. Run the focused test file and confirm the new tests fail before implementation.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py
```

**Expected result:**
Tests describe all three roadmap limits and initially fail.

**Commit suggestion:**
`feat(bridget): bound recent session injection`

### Task 2: Implement and document the boundary

**Purpose:** Keep prompt growth predictable while leaving persisted session detail unchanged.

**Files:**

- Modify: `mq-mcp/bridget_context.py`
- Modify: `ROADMAP.md`

**Steps:**

1. Select recent structured history entries using an injectable clock.
2. Render at most three entries and cap each rendered block at 500 characters.
3. Exclude invalid, future, and older-than-seven-day entries.
4. Mark the roadmap item complete and advance `Next`.
5. Run focused and full gates, then summarize without committing.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridget_runtime.py tests/test_bridge_refactor.py
./scripts/validate.sh
git diff --check
```

**Expected result:**
Only eligible bounded sessions reach the system prompt; all validation passes.

**Commit suggestion:**
`feat(bridget): bound recent session injection`
