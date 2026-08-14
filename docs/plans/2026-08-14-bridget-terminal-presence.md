# Bridget Terminal Presence Implementation Plan

## Goal

Complete Bridget Phase 5 with calm terminal status feedback and a `--quiet`
mode that removes visual effects without changing execution or approval safety.

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

- No workflow or tool-policy changes.
- No new persistence or telemetry.
- No changes to mq-agent or mqlaunch.

## Approval gates

- Before file writes: approved by the user's Phase 5 request.
- Before commit: yes, separate user request required.
- Before push/merge: yes, separate user request required.
- Before deletion/settings changes: yes; none planned.

## Test gates

- `uv --directory mq-mcp run pytest ../tests/test_bridge_refactor.py ../tests/test_bridget_gate.py -q --tb=short`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the Phase 5 commit, or restore only the files listed below before they
are committed.

### Task 1: Lock the CLI and terminal behavior with tests

**Purpose:** Define quiet parsing, labeled thinking output, response behavior,
and the approval status before implementation.

**Files:**

- Modify: `tests/test_bridge_refactor.py`
- Modify: `tests/test_bridget_gate.py`

**Steps:**

1. Add focused tests for `--quiet` and terminal rendering.
2. Run the focused tests and confirm the new assertions fail.
3. Keep safety and non-TTY behavior unchanged.

**Expected result:** New tests fail only because Phase 5 is not implemented.

### Task 2: Implement status feedback and quiet mode

**Purpose:** Make thinking, responding, and approval states explicit while
allowing scripts and users to disable visual effects.

**Files:**

- Modify: `mq-mcp/bridge.py`

**Steps:**

1. Add the `--quiet` CLI flag and help text.
2. Label the TTY spinner as thinking and show responding before the answer.
3. Label the existing mandatory approval card as approval required.
4. Disable spinner, response animation, and face rendering in quiet mode.
5. Preserve plain output, approval prompts, exit codes, and tool behavior.

**Expected result:** Interactive output has clear state, while quiet output is
immediate and contains no animation or image rendering.

### Task 3: Document and validate Phase 5

**Purpose:** Keep user documentation and roadmap status aligned with runtime.

**Files:**

- Modify: `README.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Document `--quiet` and status behavior.
2. Mark both Phase 5 items complete and advance the roadmap.
3. Run focused tests and the full validation gate.
4. Summarize the diff; do not commit.

**Expected result:** Phase 5 is documented, checked off, and all gates pass.

**Commit suggestion:**

`feat(bridget): complete terminal presence phase`
