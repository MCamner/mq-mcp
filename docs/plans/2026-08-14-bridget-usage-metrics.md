# Bridget Usage Metrics Implementation Plan

## Goal

Complete Bridget Phase 6 with local, content-free daily counters and a simple
CLI dashboard.

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

- No prompt, answer, repository, tool-argument, or transcript telemetry.
- No cloud upload, background service, scoring, or behavioral profiling.
- No changes to mq-agent, mqobsidian, or mqlaunch.

## Approval gates

- Before file writes: approved by the user's Phase 6 request.
- Before commit: separate user request required.
- Before push/merge: separate user request required.
- Before deletion/settings changes: separate approval required; none planned.

## Test gates

- `uv --directory mq-mcp run pytest ../tests/test_bridget_metrics.py ../tests/test_bridge_refactor.py -q --tb=short`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert the Phase 6 commit. The optional local `~/.mq/bridget-metrics.jsonl`
counter file may remain; deleting it is a separate explicit user action.

### Task 1: Define the metrics contract test-first

**Purpose:** Keep collection bounded to known aggregate counters and make
malformed local rows harmless.

**Files:**

- Create: `tests/test_bridget_metrics.py`
- Create: `mq-mcp/bridget_metrics.py`

**Steps:**

1. Test known-counter validation and content-free JSONL rows.
2. Test daily aggregation, date bounds, malformed rows, and dashboard output.
3. Implement a best-effort local counter store.

**Expected result:** Only dates, counter names, and integer increments persist.

### Task 2: Instrument Bridget outcomes

**Purpose:** Count completed commands and sessions, actual workflow delegation,
learn suggestions and acceptance, plus history/context hits.

**Files:**

- Modify: `mq-mcp/bridge.py`
- Modify: `scripts/validate.sh`
- Modify: `tests/test_bridge_refactor.py`

**Steps:**

1. Record counters only at verified outcome points.
2. Keep metrics failure best-effort and unable to break Bridget.
3. Add `bridget --metrics [N]` as a synchronous local command.
4. Disable collection inside repository validation and CI smoke paths.

**Expected result:** Metrics reflect outcomes without storing task content.

### Task 3: Declare persistence and close Phase 6

**Purpose:** Make the new local surface visible and keep documentation current.

**Files:**

- Modify: `README.md`
- Modify: `docs/BRIDGET_MEMORY.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Document the exact metrics path, schema, non-content boundary, and command.
2. Mark all Phase 6 roadmap items complete.
3. Run focused and full validation.

**Expected result:** Phase 6 is implemented, declared, and reproducibly tested.

**Commit suggestion:**

`feat(bridget): add local usage metrics`
