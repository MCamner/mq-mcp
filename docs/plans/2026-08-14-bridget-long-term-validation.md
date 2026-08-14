# Bridget Long-Term Validation Implementation Plan

## Goal

Start Bridget Phase 7 with a deterministic, content-free validation report and
an explicit observation protocol without claiming long-term evidence before it
exists.

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

- No prompt, answer, transcript, repository, path, or tool-argument telemetry.
- No automatic usefulness score or claim that aggregate counters prove quality.
- No new memory engine, promotion logic, cloud upload, or cross-repo writes.

## Approval gates

- Before file writes: approved by the user's Phase 7 request.
- Before commit: separate user request required.
- Before push/merge: separate user request required.
- Before deletion/settings changes: separate approval required; none planned.

## Test gates

- `uv --directory mq-mcp run pytest ../tests/test_bridget_metrics.py -q --tb=short`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the Phase 7 commit. Existing local aggregate metrics remain unchanged.

### Task 1: Define the validation report test-first

**Purpose:** Turn the existing fixed counters into transparent totals and
ratios while preserving the content-free contract.

**Files:**

- Modify: `tests/test_bridget_metrics.py`
- Modify: `mq-mcp/bridget_metrics.py`

**Steps:**

1. Test zero-data, partial-data, ratio, and command-boundary behavior.
2. Add `bridget --validation [1-365]` using the existing metrics store.
3. State explicitly which Phase 7 questions aggregate counters cannot answer.

**Expected result:** The report is deterministic and never overstates evidence.

### Task 2: Document the observation protocol

**Purpose:** Define what evidence is required before Phase 7 can be completed.

**Files:**

- Create: `docs/BRIDGET_VALIDATION.md`
- Modify: `README.md`
- Modify: `docs/BRIDGET_MEMORY.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Document quantitative signals and qualitative review questions.
2. Record privacy, ownership, and decision boundaries.
3. Mark Phase 7 in progress, leaving real long-term evidence unchecked.

**Expected result:** Phase 7 is executable but not falsely marked complete.

**Commit suggestion:**

`feat(bridget): add long-term validation baseline`
