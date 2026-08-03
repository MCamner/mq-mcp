# Model Routing MCP Tools Implementation Plan

## Goal

Expose the mq-agent model router through five validated, read-only MCP tools.

## Owner repo

mq-mcp

## Secondary repos

mq-agent is a runtime dependency and remains the routing-policy owner.

## Architecture boundary

- mq-agent owns classification, policy, shadow execution, and route reports.
- mq-mcp owns MCP exposure, tool safety, and deterministic candidate verification.
- mqobsidian persistence, HAL presentation, and mqlaunch routing remain out of scope.
- Model output is untrusted data and is never executed or stored by these tools.

## Non-goals

- No repository writes, outcome persistence, model-generated commands, or automatic approval.
- No duplicated routing thresholds or task-class policy in mq-mcp.

## Approval gates

- Before file writes: approved by the request to continue the roadmap.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

- `uv run pytest -q tests/test_model_routing_tools.py`
- `uv run pytest -q`
- `uv run ruff check .`
- `./scripts/validate.sh`
- `git diff --check`

## Rollback

Revert this PR. mq-agent routing commands remain independently usable.

### Task 1: Add the fixed mq-agent bridge

Create `mq-mcp/model_routing.py` with fixed command construction, JSON parsing,
structured unavailable results, and no shell execution.

### Task 2: Add five MCP tools and verification

Register `mq_route_inspect`, `mq_route_shadow`, `mq_context_pack`,
`mq_route_verify`, and `mq_route_report`. Validate every returned envelope and
reject malformed or mismatched candidates.

### Task 3: Update safety contracts and profiles

Classify all five tools as Class B read-only, regenerate machine-readable
contracts, add them to both Codex and Claude profiles, and update tool docs.

### Task 4: Prove degraded mode

Use mocked contract tests to prove that all tools load without Ollama and that
missing mq-agent/Ollama paths return structured `UNAVAILABLE` results.

**Commit suggestion:**

`feat(routing): expose validated read-only MCP tools`
