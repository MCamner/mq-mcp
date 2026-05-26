# MCP Server Profiles

`mq-mcp` ships versioned JSON profile templates in `profiles/`.

Profiles are not hidden automation. They are copyable configuration templates
that make client setup explicit: command, args, environment, recommended tools,
and safety notes live in one place.

## Commands

```bash
mq-mcp profiles list
mq-mcp profiles show read-only
mq-mcp profiles path
mq-mcp profiles validate
```

The validation command runs the same contract check used by `scripts/validate.sh`.

## Available Profiles

| Profile | Best for | Client |
| --- | --- | --- |
| `read-only` | Safe repo inspection and safety review | Generic |
| `repo-only` | Repo-scoped development inside `mq-mcp` | Generic |
| `developer` | Multi-repo mq ecosystem development | Generic |
| `local-macos` | macOS app, clipboard, notification, and local helper workflows | Generic |
| `mq-agent` | mq-agent discovery, safety display, dry-run, and local repo workflows | mq-agent |
| `openai-bridge` | Bridget / `bridge.py` prompt workflows | OpenAI bridge |
| `claude-desktop` | Claude Desktop `mcpServers` setup | Claude Desktop |
| `codex` | Codex repo-aware local MCP sessions | Codex |

## Choosing a Profile

Start with the smallest profile that can do the job.

Use `read-only` when you only need inspection. It grants no extra repos or
external paths.

Use `repo-only` when you need validation or exact-match edits inside this repo.

Use `developer` when working across registered mq ecosystem repositories.

Use `local-macos` only when local app or system helper tools are useful.

Use `mq-agent`, `openai-bridge`, `claude-desktop`, or `codex` when configuring
that specific client surface.

## Placeholders

Templates use placeholders so they can be committed safely:

```text
{{MQ_MCP_REPO_ROOT}}
{{MQ_MCP_APP_DIR}}
{{MQ_HAL_REPO}}
{{REPO_SIGNAL_REPO}}
{{MACOS_SCRIPTS_REPO}}
```

Replace placeholders with absolute paths in local client configs. Do not commit
machine-specific paths, API keys, or real secrets.

## Claude Desktop

Inspect the template:

```bash
mq-mcp profiles show claude-desktop
```

Copy the `mcpServers` object into:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Replace placeholder paths, then restart Claude Desktop.

## Codex

Use the `codex` profile when Codex needs repo inspection, validation, safety
metadata, and mq ecosystem context.

```bash
mq-mcp profiles show codex
```

Keep write-capable tools explicit and review diffs before committing.

## mq-agent

The `mq-agent` profile is designed for:

- tool discovery
- safety class display
- dry-run behavior
- mq-hal and repo-signal integration

```bash
mq-mcp profiles show mq-agent
```

mq-agent should continue to approval-gate unsafe subprocess and write-capable
tool calls.

## OpenAI Bridge

The `openai-bridge` profile documents the Bridget / `bridge.py` workflow.

It intentionally does not store `OPENAI_API_KEY`. Keep API credentials in your
local shell environment or uncommitted `.env`.

## Validation

Run:

```bash
./scripts/check-profiles.py
./scripts/validate.sh
```

Profile validation checks:

- JSON parses cleanly
- filenames match profile names
- required fields are present
- expected profile names exist
- command args, env, recommended tools, and safety notes have useful shape
