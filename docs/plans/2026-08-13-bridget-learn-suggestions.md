# Bridget Learn Suggestions Implementation Plan

## Goal

Show one bounded, read-only reusable-learning suggestion after evidence-producing
Bridget sessions without invoking or writing any learn store.

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

Bridget may suggest a candidate based on session context. It must not call a
Class C learn tool, persist the suggestion, or treat the session as evidence.

## Non-goals

- Automatic extraction, storage, promotion, or scoring.
- A new MCP tool or learn schema.
- The later `--learn-last` approval workflow.

## Approval gates

- Before file writes: approved by the user request.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/bridge.py`,
`tests/test_bridge_refactor.py`, and `ROADMAP.md`.

### Task 1: Define suggestion eligibility

**Purpose:** Ensure suggestions appear only after evidence-producing tools.

**Files:**

- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Test review/test/validation tool eligibility.
2. Test that ordinary or empty sessions produce no suggestion.
3. Test bounded output and explicit `stored: false` wording.

**Expected result:** Tests fail for the missing suggestion helper.

### Task 2: Emit one preview-only suggestion

**Purpose:** Add a useful end-of-session hint without side effects.

**Files:**

- Modify: `mq-mcp/bridge.py`

**Steps:**

1. Build a deterministic candidate from bounded prompt/answer excerpts.
2. Emit it after one-shot sessions and once at REPL exit.
3. Point to dry-run review before any approved storage.

**Expected result:** The helper performs no MCP, model, or filesystem call.

### Task 3: Synchronize roadmap and validate

**Purpose:** Mark only the shipped suggestion behavior complete.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full tests.
2. Mark the suggestion checkbox complete.
3. Point next status to `bridget --learn-last`.

**Expected result:** Roadmap and implementation agree.

**Commit suggestion:**

`feat(bridget): suggest reusable learn candidates`
