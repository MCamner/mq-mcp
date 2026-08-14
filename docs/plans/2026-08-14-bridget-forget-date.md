# Bridget Forget Date Implementation Plan

## Goal

Add `bridget --forget YYYY-MM-DD` as a preview-first, explicitly approved deletion of exactly one date from Bridget's temporary session stores.

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

The command may delete Bridget temporary session data only. It must never touch learn memory, mqobsidian, reviews, or another date.

## Non-goals

- Bulk/range deletion or retention policies.
- Deleting lessons, review history, or mqobsidian notes.
- Changing bounded session injection.

## Approval gates

- Before file writes: approved by the user's roadmap instruction.
- Before runtime deletion: explicit terminal confirmation every time.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes during implementation: yes; tests use temporary files only.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridget_runtime.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/bridget_context.py`, `mq-mcp/bridget_runtime.py`, `mq-mcp/bridge.py`, their tests, `ROADMAP.md`, and this plan. Session data deleted by a real approved invocation cannot be recovered by code rollback.

### Task 1: Lock exact-date deletion semantics

**Purpose:** Prevent traversal, wildcard, cross-date, and partial-surface behavior.

**Files:**

- Modify: `tests/test_bridget_context.py`

**Steps:**

1. Test strict `YYYY-MM-DD` validation.
2. Test dry-run counts without mutation.
3. Test approved deletion from daily JSONL, legacy history, and rolling markdown.
4. Test preservation of every other date.

**Expected result:** Tests initially fail because no forget API exists.

### Task 2: Add the guarded CLI route

**Purpose:** Expose deletion with a clear preview and deny-by-default prompt.

**Files:**

- Modify: `mq-mcp/bridget_context.py`
- Modify: `mq-mcp/bridget_runtime.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `tests/test_bridget_runtime.py`

**Steps:**

1. Compute exact-date counts without changing files.
2. Show affected surfaces and state that deletion is irreversible.
3. Accept only explicit yes words; empty, EOF, and other input deny.
4. Delete/rewrite only after approval and report the exact result.

**Expected result:** `--forget` never starts OpenAI/MCP and cannot delete without confirmation.

### Task 3: Synchronize roadmap and validate

**Purpose:** Mark only date deletion complete and identify bounded session injection next.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full validation.
2. Mark `bridget --forget <date>` complete.
3. Point next status to bounded recent-session injection.

**Expected result:** Roadmap and verified runtime behavior agree.

**Commit suggestion:**

`feat(bridget): add date-scoped session deletion`
