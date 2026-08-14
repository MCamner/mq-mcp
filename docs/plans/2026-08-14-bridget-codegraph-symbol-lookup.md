# Bridget CodeGraph Symbol Lookup Implementation Plan

## Goal

Add a read-only `bridget --symbol` command that delegates symbol lookup to the supported CodeGraph CLI.

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

- Reading `.codegraph/codegraph.db` directly.
- Persisting graph output or treating it as evidence.
- Implementing dependency or hotspot lookup in the same change.

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

Remove the lookup module and its bridge dispatch/help wiring, then revert the roadmap checkbox and docs.

### Task 1: Define the CLI contract

**Purpose:** Lock argument validation, safe delegation, stdout/stderr, and exit-code behavior before implementation.

**Files:**

- Create: `tests/test_codegraph_lookup.py`

**Steps:**

1. Test `--symbol NAME`, optional `--repo`, and optional `--file`.
2. Reject missing, duplicate, and unknown arguments before subprocess execution.
3. Verify an argv-list call to `codegraph --no-color node` and delegated exit codes.
4. Run the focused tests and confirm failure before implementation.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py
```

**Expected result:**

Tests fail because the lookup module does not yet exist.

**Commit suggestion:**

`feat(bridget): add CodeGraph symbol lookup`

### Task 2: Implement and expose symbol lookup

**Purpose:** Provide a deterministic, headless, read-only symbol command without OpenAI or MCP startup.

**Files:**

- Create: `mq-mcp/codegraph_lookup.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `README.md`
- Modify: `docs/global/GLOBAL_COMMAND_SURFACE.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Resolve the selected, pinned, or current Git repository.
2. Invoke `codegraph --no-color node` with an argument list and timeout.
3. Preserve stdout, stderr, and delegated non-zero exit codes.
4. Intercept the command before OpenAI/MCP startup.
5. Document the exact command and mark only Symbol lookup complete.
6. Run focused and full validation plus a real read-only entrypoint smoke test.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py tests/test_bridge_refactor.py
uv --directory mq-mcp run python bridge.py --symbol BridgetContext --file mq-mcp/bridget_context.py
./scripts/validate.sh
git diff --check
```

**Expected result:**

The symbol command prints CodeGraph's source/call trail without creating files, and all gates pass.

**Commit suggestion:**

`feat(bridget): add CodeGraph symbol lookup`
