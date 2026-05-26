# mq-mcp Integration Map

This document explains how `mq-mcp`, `mq-hal`, and `repo-signal` fit together.

## Goal

`mq-mcp` acts as the local MCP bridge layer.

Together, the stack becomes:

```text
mq-mcp + mq-hal + repo-signal
= local AI assistant + safe repo analysis + publish-quality checks
```

## Roles

| Project | Role |
| --- | --- |
| `mq-mcp` | Local MCP server, bridge, packaged CLI, and safe tool layer |
| `mq-hal` | Local assistant / operator layer for asking, auditing, and reporting |
| `repo-signal` | Repository quality, readiness, and publishability checks |
| `mqlaunch` | macOS menu and terminal launcher for starting local workflows |

## Main integration tools

| MCP tool | Purpose | Safety profile |
| --- | --- | --- |
| `hal_repo_report` | Runs a read-only mq-hal repo report | Read-only |
| `repo_signal_analyze` | Runs repo-signal analysis on a local repo | Read-only |
| `repo_signal_checklist` | Runs repo-signal publish checklist on a local repo | Read-only |
| `tool_safety_report` | Shows documented MCP tool safety classes | Read-only |
| `list_local_repos` | Lists registered local repos from `MQ_MCP_LOCAL_REPOS` | Read-only |
| `open_repo_terminal` | Opens a registered repo in Terminal | Local action |

## Recommended local repo registration

Use `MQ_MCP_LOCAL_REPOS` to register known repos by name.

Example:

```bash
export MQ_MCP_LOCAL_REPOS="/Users/mansys/repo-signal,/Users/mansys/mq-hal,/Users/mansys/macos-scripts"
```

Do not use this for arbitrary system paths.

## Example prompts

### Ask Bridget for repo status

```bash
bridget "run hal repo report for mq-mcp"
```

### Ask for repo-signal analysis

```bash
bridget "run repo signal analyze for mq-mcp"
```

### Ask for publish checklist

```bash
bridget "run repo signal checklist for mq-mcp"
```

### Ask for safety map

```bash
bridget "show tool safety report"
```

### Start from mqlaunch

```bash
mqlaunch agent mcp-status
mqlaunch agent mcp-tools
```

Target flow:

```text
mqlaunch
  -> mq-agent
  -> mq-mcp
  -> safe local tool execution
```

## Safety rules

The integration should stay local-first and explicit.

1. Default to read-only tools.
2. Keep repo access scoped through registered local repositories.
3. Do not run destructive commands without explicit user approval.
4. Do not commit secrets, tokens, private machine paths, or `.env` files.
5. Keep write-capable tools documented in `docs/TOOL_SAFETY.md`.
6. Validate documentation whenever a new MCP tool is added.

## Integration smoke test

Run from the repository root:

```bash
./scripts/check-integration-smoke.sh
./scripts/check-bridge-tool-discovery.sh
```

The smoke test verifies that the main integration tools are present in:

- `mq-mcp/server.py`
- `README.md`
- `docs/integration.md`
- `docs/TOOL_SAFETY.md`
- `scripts/validate.sh`

This protects the public integration story from drifting away from the actual MCP server implementation.

The bridge tool discovery check also verifies that `bridge.py --tools` exposes the same integration tools to Bridget before any OpenAI prompt is needed.

## v0.3.0 direction

A good v0.3.0 theme:

```text
safer local assistant workflows
```

Recommended release contents:

- documented `mq-mcp + mq-hal + repo-signal` integration
- validation guard for integration docs
- safety map for all MCP tools
- demo prompts for Bridget
- clearer repo registration examples
