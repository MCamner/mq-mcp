# Bridget Recent Work Context Implementation Plan

## Goal

Inject a bounded summary of the latest review and current Git diff into
Bridget's project context.

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

Bridget reads transient local state only. The context is neither persisted nor
treated as durable evidence.

## Non-goals

- Injecting full patch content.
- Persisting reviews, diffs, or generated summaries.
- Selecting workflows or promoting learning.

## Approval gates

- Before file writes: approved by the user request.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_runtime.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/bridget_runtime.py`,
`tests/test_bridget_runtime.py`, and `ROADMAP.md`.

### Task 1: Define the bounded contract

**Purpose:** Lock the content, compatibility, and size limit before implementation.

**Files:**

- Modify: `tests/test_bridget_runtime.py`
- Read-only reference: `mq-mcp/bridget_runtime.py`

**Steps:**

1. Test latest-review selection for legacy and repo-namespaced history.
2. Test clean and dirty Git repositories.
3. Test the 1,200-character hard limit.

**Expected result:** Focused tests fail only for missing recent-work behavior.

### Task 2: Implement recent-work context

**Purpose:** Add useful current-work orientation without prompt growth or raw patches.

**Files:**

- Modify: `mq-mcp/bridget_runtime.py`

**Steps:**

1. Read the latest compatible review metadata.
2. Read `git diff --stat` rather than patch bodies.
3. Build and truncate the block to 1,200 characters.
4. Include it in the existing project context.

**Expected result:** Bridget receives review and diff summaries with no new writes.

### Task 3: Synchronize roadmap and validate

**Purpose:** Mark only verified work complete.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full validation.
2. Mark recent-work injection complete.
3. Point current status to the next remaining Phase 3 item.

**Expected result:** Roadmap matches tested behavior.

**Commit suggestion:**

`feat(bridget): inject bounded recent work context`
