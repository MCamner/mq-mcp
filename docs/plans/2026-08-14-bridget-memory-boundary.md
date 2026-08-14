# Bridget Memory Boundary Implementation Plan

## Goal

Make Bridget's temporary-session boundary inspectable and verify that recording a session creates no hidden persistence or learning evidence.

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

- Adding a new memory command or storage backend.
- Changing retention or deletion behavior.
- Promoting session text to learning or mqobsidian.

## Approval gates

- Before file writes: approved by the user's roadmap instruction
- Before commit: yes
- Before push/merge: yes
- Before deletion/settings changes: yes

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the boundary documentation, characterization tests, and roadmap status together.

### Task 1: Verify the persistence boundary

**Purpose:** Prove that normal session recording writes only the three declared temporary session surfaces.

**Files:**

- Modify: `tests/test_bridget_context.py`
- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Record a session in an isolated directory.
2. Assert the exact set of created files.
3. Assert a session without an evidence-producing tool cannot suggest learning.
4. Run focused tests.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_bridget_context.py tests/test_bridge_refactor.py
```

**Expected result:**

Only the rolling markdown, legacy history, and dated JSONL file exist; no learn suggestion is produced from session context alone.

**Commit suggestion:**

`docs(bridget): define temporary memory boundary`

### Task 2: Publish the contract and close Phase 2.5

**Purpose:** Give operators one source of truth for retention, deletion, evidence, and commands.

**Files:**

- Create: `docs/BRIDGET_MEMORY.md`
- Modify: `README.md`
- Modify: `docs/LEARNING_CONTRACT.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Document every Bridget-owned local persistence path and its purpose.
2. Document the existing history, forget, continue, project, and learn-last commands.
3. State that session logs are context, never evidence, and never auto-promote.
4. Mark Phase 2.5 complete and advance `Next`.
5. Run the full validation gate and summarize without committing.

**Commands:**

```bash
./scripts/validate.sh
git diff --check
```

**Expected result:**

The implemented command and persistence surfaces match the docs, and Phase 2.5 is complete.

**Commit suggestion:**

`docs(bridget): define temporary memory boundary`
