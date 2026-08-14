# Bridget Daily Session Logs Implementation Plan

## Goal

Write each completed Bridget session to `bridget_memory/sessions/YYYY-MM-DD.jsonl` while keeping current history behavior compatible and secret-redacted.

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

Daily session files are temporary Bridget working memory, not durable knowledge or evidence.

## Non-goals

- `bridget --forget <date>` deletion.
- Reading daily files into prompts.
- Migrating or deleting the existing append-only history file.
- Promoting sessions into learning automatically.

## Approval gates

- Before file writes: approved by the user's roadmap instruction.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridget_runtime.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/bridget_context.py`, its tests, `ROADMAP.md`, and this plan. Existing user-created daily logs are data and are not deleted by rollback.

### Task 1: Define the daily file contract

**Purpose:** Lock filename, JSON shape, one-entry behavior, and redaction before implementation.

**Files:**

- Modify: `tests/test_bridget_context.py`
- Modify: `tests/test_bridget_runtime.py`

**Steps:**

1. Test `YYYY-MM-DD.jsonl` selection from the session timestamp.
2. Test one identical logical entry in legacy and daily history.
3. Test redaction in JSONL and rolling markdown.
4. Test best-effort failure isolation.

**Expected result:** Tests initially fail because the daily store does not exist.

### Task 2: Append redacted daily sessions

**Purpose:** Add date-partitioned temporary working memory without changing readers.

**Files:**

- Modify: `mq-mcp/bridget_context.py`

**Steps:**

1. Derive the daily directory from the configured history directory by default.
2. Build one redacted entry and append it to both stores.
3. Use one timestamp for filename, JSON, and rolling markdown.
4. Keep each write independently best-effort.

**Expected result:** Current callers and `--history` remain compatible.

### Task 3: Synchronize roadmap and validate

**Purpose:** Mark only per-day logging complete and identify the next deletion workflow.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full validation.
2. Mark per-day session logs complete.
3. Point next status to `bridget --forget <date>`.

**Expected result:** Roadmap and verified runtime behavior agree.

**Commit suggestion:**

`feat(bridget): write daily session logs`
