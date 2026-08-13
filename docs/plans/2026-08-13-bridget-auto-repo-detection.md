# Bridget Auto Repo Detection Implementation Plan

## Goal

Let Bridget inject the current Git repository, branch, and dirty-file summary
when no project has been pinned explicitly.

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

Bridget detects only the current local Git working context. It does not select a
workflow, persist knowledge, or override an explicit project pin.

## Non-goals

- Recent-review or diff-content injection.
- Cross-repository selection or delegation.
- Changes to mqobsidian, mq-agent, or CodeGraph.

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

### Task 1: Lock automatic detection behavior

**Purpose:** Define pin precedence, Git-root discovery, and non-repo fallback.

**Files:**

- Modify: `tests/test_bridget_runtime.py`
- Read-only reference: `mq-mcp/bridget_runtime.py`

**Steps:**

1. Add failing tests for automatic repo context.
2. Confirm the focused test fails for the missing behavior.

**Expected result:** Tests specify that an explicit pin wins and an unpinned Git
working directory is detected without persistence.

### Task 2: Implement bounded auto context

**Purpose:** Inject existing `repo_brief` data for the detected repository.

**Files:**

- Modify: `mq-mcp/bridget_runtime.py`
- Modify: `tests/test_bridget_runtime.py`

**Steps:**

1. Resolve the current Git top-level directory read-only.
2. Use it only when no valid explicit pin exists.
3. Reuse the bounded branch/dirty-file summary.
4. Run focused tests.

**Expected result:** Bridget starts with accurate local repo context and degrades
to an empty block outside Git repositories.

### Task 3: Synchronize roadmap and validate

**Purpose:** Remove stale roadmap status and mark only verified work complete.

**Files:**

- Modify: `ROADMAP.md`

**Steps:**

1. Mark Phase 0 done.
2. Replace the completed recommended-next-step text.
3. Mark auto repo detection complete after tests pass.
4. Run full validation and summarize the diff.

**Expected result:** Roadmap status matches tested repository behavior.

**Commit suggestion:**

`feat(bridget): detect current repository context`
