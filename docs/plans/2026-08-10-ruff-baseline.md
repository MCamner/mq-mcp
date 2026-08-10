# Ruff Baseline Implementation Plan

## Goal

Establish a small, passing Ruff correctness gate for mq-mcp and run it in validation and CI.

## Owner repo

mq-mcp

## Secondary repos

None.

## Architecture boundary

- mq-mcp owns execution tools, tool safety, and runtime boundaries.
- This change affects repository quality gates only; it does not change MQ runtime ownership.

## Non-goals

- Enabling broad style, modernization, complexity, or annotation rules.
- Renaming legacy one-letter locals or rewriting compact control flow.
- Refactoring unrelated runtime behavior.

## Approval gates

- Before file writes: approved by the user request.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: not applicable.

## Test gates

- `uv --directory mq-mcp run ruff check --no-cache --config pyproject.toml . ../review_engine ../semantic_memory ../scripts ../tests`
- `./scripts/validate.sh`

## Rollback

Revert this plan, the Ruff configuration, the validation section, and only the mechanical baseline fixes made for this task.

### Task 1: Define the initial Ruff policy

**Purpose:** Adopt correctness-focused linting without pulling legacy style debt into the first gate.

**Files:**

- Modify: `mq-mcp/pyproject.toml`

### Task 2: Clear the selected baseline

**Purpose:** Fix all findings enforced by the initial policy.

**Files:**

- Modify: only Python files reported by the configured Ruff command.

### Task 3: Add the validation gate

**Purpose:** Make local validation and existing CI enforce the same policy.

**Files:**

- Modify: `scripts/validate.sh`

**Commit suggestion:**

`chore(quality): establish minimal Ruff baseline`
