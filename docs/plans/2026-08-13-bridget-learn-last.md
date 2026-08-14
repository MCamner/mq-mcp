# Bridget Learn Last Implementation Plan

## Goal

Add `bridget --learn-last` as a redacted preview-first workflow with an explicit approval gate before learning storage.

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

Bridget may preview a candidate from current review or diff evidence. Storage stays in mq-mcp's existing learn tools and requires a separate approval.

## Non-goals

- New learn schemas, stores, or MCP tools.
- Automatic promotion or storage.
- Changes to mqobsidian or mq-agent.

## Approval gates

- Before file writes: approved by the user's roadmap instruction.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.
- Before learning storage at runtime: always.

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the focused changes to `mq-mcp/bridge.py`, `tests/test_bridge_refactor.py`, `ROADMAP.md`, and this plan.

### Task 1: Lock the CLI and safety contract

**Purpose:** Define preview-first selection, redaction, and denial behavior before implementation.

**Files:**

- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Test argument parsing and latest-review selection.
2. Test that preview output is redacted.
3. Test that denial performs no storage call and approval uses the existing gated learn tool.

**Expected result:** Tests fail for the missing workflow.

### Task 2: Implement the bounded workflow

**Purpose:** Reuse existing review/diff evidence and learn tools without adding storage paths.

**Files:**

- Modify: `mq-mcp/bridge.py`

**Steps:**

1. Intercept `--learn-last` before the normal model flow.
2. Build and print a bounded, secret-redacted preview.
3. Ask explicitly before dispatching the existing Class C learn tool.
4. Preserve dry-run behavior when approval is denied or unavailable.

**Expected result:** No learning is stored before an explicit yes.

### Task 3: Synchronize roadmap and validate

**Purpose:** Keep roadmap status aligned with verified behavior.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Run focused and full validation.
2. Mark only `--learn-last` complete.
3. Point next status to learning provenance.

**Expected result:** Tests and documentation agree.

**Commit suggestion:**

`feat(bridget): add learn-last preview workflow`
