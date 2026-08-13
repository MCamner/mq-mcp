# Context-Aware Lesson Injection Implementation Plan

## Goal

Inject only repo-, risk-, file-, and task-relevant lessons into Bridget with a fixed total character budget.

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

This change filters mq-mcp's existing local lesson store for runtime prompt context. It does not create knowledge or treat session text as evidence.

## Non-goals

- Semantic/vector search or a new memory store.
- Changing lesson persistence, provenance, or promotion.
- Adding session logs or hidden persistence.

## Approval gates

- Before file writes: approved by the user's roadmap instruction.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/bridget_context.py`, `mq-mcp/bridge.py`, their tests, `ROADMAP.md`, and this plan.

### Task 1: Lock filtering and budget behavior

**Purpose:** Define deterministic selection before changing runtime prompts.

**Files:**

- Modify: `tests/test_bridget_context.py`

**Steps:**

1. Test repo and risk filtering.
2. Test task, tag, and file relevance.
3. Test legacy record compatibility, deduplication, and the total character cap.

**Expected result:** Tests initially fail because `load_lessons` lacks context parameters.

### Task 2: Refresh bounded context per task

**Purpose:** Keep one relevant lesson block without growing REPL history.

**Files:**

- Modify: `mq-mcp/bridget_context.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Rank eligible lessons deterministically from local JSONL fields.
2. Bound the complete rendered block, not only individual lessons.
3. Derive active repo and an optional file path from the current task.
4. Replace the REPL system message's context each turn.

**Expected result:** One-shot and each REPL turn receive current bounded lessons without accumulation.

### Task 3: Synchronize roadmap and validate

**Purpose:** Mark Phase 1 complete only after repository validation.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full validation.
2. Mark context-aware lesson injection complete.
3. Point next status to the next remaining roadmap phase.

**Expected result:** Roadmap and verified runtime behavior agree.

**Commit suggestion:**

`feat(bridget): filter injected lessons by context`
