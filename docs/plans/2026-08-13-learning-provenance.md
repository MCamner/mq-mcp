# Learning Provenance Implementation Plan

## Goal

Add explicit, validated `learning_origin` metadata to local learning records while preserving existing `source` semantics and legacy records.

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

The local mq-mcp learn store owns this provenance field. It does not change mqobsidian's `learn.v1` contract.

## Non-goals

- Migrating or rewriting historical JSONL records.
- Changing fingerprints or duplicate detection.
- Context-aware lesson injection.

## Approval gates

- Before file writes: approved by the user's roadmap instruction.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_learn_engine.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/learn_engine.py`, `mq-mcp/server.py`, `mq-mcp/bridge.py`, their tests, `ROADMAP.md`, and this plan.

### Task 1: Define the provenance contract

**Purpose:** Lock allowed origins and backward-compatible defaults before implementation.

**Files:**

- Modify: `tests/test_learn_engine.py`

**Steps:**

1. Test `user`, `bridget`, `review`, and `diff` origins.
2. Test default inference from legacy `source` values.
3. Test rejection of unsupported origins.

**Expected result:** Tests initially fail because `learning_origin` does not exist.

### Task 2: Wire every local write path

**Purpose:** Preserve provenance from manual, review, diff, and Bridget workflows.

**Files:**

- Modify: `mq-mcp/learn_engine.py`
- Modify: `mq-mcp/server.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Add the field to `LearningRecord` and validate it in `make_learning`.
2. Default direct records to `user`, review records to `review`, and diff records to `diff`.
3. Pass `bridget` from `--learn-last` storage calls.
4. Leave existing JSONL records readable without migration.

**Expected result:** New records carry one allowed origin and existing callers remain valid.

### Task 3: Synchronize roadmap and validate

**Purpose:** Keep shipped status and next work accurate.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full validation.
2. Mark learning provenance complete.
3. Point the next status to context-aware lesson injection.

**Expected result:** Roadmap and runtime behavior agree.

**Commit suggestion:**

`feat(learn): record learning provenance`
