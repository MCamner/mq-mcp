# Bridget Auto-Delegation Suggestion Implementation Plan

## Goal

Suggest the existing mq-agent workflow entrypoint for clearly multi-step, cross-repo, or complex prompts without starting delegation automatically.

## Owner repo

mq-mcp

## Secondary repos

mq-agent (read-only contract reference)

## Architecture boundary

- mqobsidian owns context contracts, templates, generators, and published context surfaces.
- mq-agent owns planning, workflow routing, task decomposition, and agent handoff.
- mq-mcp owns execution tools, tool safety, and runtime boundaries.
- mq-hal owns status, operator summaries, release/runbook views.
- repo-signal owns publish readiness, security/readiness scoring, and repo health checks.

## Non-goals

- Automatically starting `bridget --workflow` or mq-agent.
- Adding workflow state, retries, tool selection, or new templates to Bridget.
- Changing mq-agent routing or workflow contracts.

## Approval gates

- Before file writes: approved by the user's roadmap instruction
- Before commit: yes
- Before push/merge: yes
- Before deletion/settings changes: yes

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_bridget_workflow.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Remove the pure classifier/rendering helpers and their two output call sites, then revert docs and the roadmap checkbox.

### Task 1: Specify conservative suggestion rules

**Purpose:** Make recommendations deterministic, explainable, bounded, and quiet for ordinary local tasks.

**Files:**

- Modify: `tests/test_bridget_workflow.py`
- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Test explicit cross-repo language and two named MQ repositories.
2. Test ordered multi-step prompts and prompts with at least three action verbs.
3. Test suppression for simple tasks and existing workflow invocation text.
4. Test that the suggestion says preview only and never claims execution.
5. Run focused tests before implementation.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_bridget_workflow.py tests/test_bridge_refactor.py
```

**Expected result:**

New tests fail until the pure suggestion helpers exist.

**Commit suggestion:**

`feat(bridget): suggest mq-agent delegation`

### Task 2: Surface one preview-only recommendation

**Purpose:** Help users discover delegation while keeping every actual workflow behind the existing explicit command and approval gate.

**Files:**

- Modify: `mq-mcp/bridget_workflow.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `README.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Implement pure reason classification and bounded rendering.
2. Print at most one recommendation per one-shot run or chat session.
3. Do not call mq-agent, mutate state, or alter the answer.
4. Document the behavior and mark only auto-suggest complete.
5. Run focused/full gates and a real prompt smoke test with a stubbed model boundary if needed.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_bridget_workflow.py tests/test_bridge_refactor.py
./scripts/validate.sh
git diff --check
```

**Expected result:**

Complex prompts receive one actionable `bridget --workflow` suggestion; simple prompts receive none; no workflow starts.

**Commit suggestion:**

`feat(bridget): suggest mq-agent delegation`
