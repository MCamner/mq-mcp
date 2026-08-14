# Bridget CodeGraph Dependency Lookup Implementation Plan

## Goal

Add a read-only `bridget --dependencies` command for bounded CodeGraph caller and callee lookup.

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

- Direct access to `.codegraph/codegraph.db`.
- Impact, hotspot, or generalized call-graph search.
- Persistence or use as observation evidence.

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

Remove dependency parsing/dispatch/docs and revert only the dependency roadmap checkbox.

### Task 1: Specify dependency CLI behavior

**Purpose:** Define safe arguments, bounded output, delegation order, and exit behavior.

**Files:**

- Modify: `tests/test_codegraph_lookup.py`

**Steps:**

1. Test callers, callees, and the default combined direction.
2. Test `--repo`, `--direction`, and a numeric `--limit` bounded to 1–100.
3. Verify exact argv-list subprocess calls and first-error exit propagation.
4. Run focused tests before implementation.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py
```

**Expected result:**

New tests fail until dependency lookup is implemented.

**Commit suggestion:**

`feat(bridget): add CodeGraph dependency lookup`

### Task 2: Implement and expose dependency lookup

**Purpose:** Make incoming and outgoing symbol dependencies discoverable without OpenAI, MCP, or database access.

**Files:**

- Modify: `mq-mcp/codegraph_lookup.py`
- Modify: `mq-mcp/bridge.py`
- Modify: `README.md`
- Modify: `docs/global/GLOBAL_COMMAND_SURFACE.md`
- Modify: `ROADMAP.md`

**Steps:**

1. Reuse the symbol lookup repository resolver and CodeGraph executable boundary.
2. Delegate to `codegraph callers` and/or `codegraph callees` with `--no-color` and timeout.
3. Preserve diagnostics and non-zero exit codes.
4. Update help/docs and mark Dependency lookup complete.
5. Run real valid/invalid entrypoint tests and the full validation gate.

**Commands:**

```bash
mq-mcp/.venv/bin/pytest -q tests/test_codegraph_lookup.py tests/test_bridge_refactor.py
uv --directory mq-mcp run python bridge.py --dependencies build_system_content --direction both --limit 5
./scripts/validate.sh
git diff --check
```

**Expected result:**

Bridget prints bounded callers and callees using supported CodeGraph CLI commands, and all gates pass.

**Commit suggestion:**

`feat(bridget): add CodeGraph dependency lookup`
