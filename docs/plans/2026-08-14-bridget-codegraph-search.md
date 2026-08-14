# Bridget CodeGraph Call-Graph Search Implementation Plan

## Goal

Add a bounded `bridget --graph-search` command backed by CodeGraph Explore for hotspot and call-path questions.

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

- Inventing a CodeGraph hotspot API.
- Falling back to direct SQLite or `codegraph files`, which is unavailable in the current execution environment.
- Persisting graph output or treating it as evidence.

## Approval gates

- Before file writes: approved by the user's roadmap instruction
- Before commit: yes
- Before push/merge: yes
- Before deletion/settings changes: yes

## Test gates

- `mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py tests/test_bridge_refactor.py`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Remove graph-search parsing/dispatch/docs and revert the Phase 3.5 status.

### Task 1: Define the graph-search CLI contract

**Purpose:** Bound query arguments, source-file count, delegation, and errors.

**Files:**

- Modify: `tests/test_codegraph_lookup.py`

**Steps:**

1. Test `--graph-search QUERY`, optional `--repo`, and `--max-files 1–20`.
2. Reject missing, duplicate, unknown, and out-of-range arguments.
3. Verify exact delegation to `codegraph --no-color explore`.
4. Verify timeout and delegated errors retain non-zero exits.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py
```

**Expected result:**

New tests fail before graph-search implementation.

**Commit suggestion:**

`feat(bridget): add CodeGraph call-graph search`

### Task 2: Implement and close Phase 3.5

**Purpose:** Expose supported CodeGraph Explore for hotspot and call-path questions without database access.

**Files:**

- Modify: `mq-mcp/codegraph_lookup.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `README.md`
- Modify: `docs/global/GLOBAL_COMMAND_SURFACE.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Delegate safely to CodeGraph Explore with the shared repo resolver and timeout.
2. Intercept before OpenAI and MCP startup and preserve output/exit behavior.
3. Document hotspot and call-path examples without claiming a dedicated hotspot API.
4. Mark Phase 3.5 done and advance `Next` to Phase 4 delegation suggestions.
5. Run real valid/invalid CLI checks and full validation.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py tests/test_bridge_refactor.py
uv --directory mq-mcp run python bridge.py --graph-search "call-graph hotspots in Bridget" --max-files 5
./scripts/validate.sh
git diff --check
```

**Expected result:**

Graph search returns CodeGraph source and call paths through the supported Explore interface, and all gates pass.

**Commit suggestion:**

`feat(bridget): add CodeGraph call-graph search`
