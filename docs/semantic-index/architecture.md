# mq-mcp Architecture

## Overview

mq-mcp is a local MCP (Model Context Protocol) server for macOS with an OpenAI bridge.

```text
User terminal
    │
    ├─ bridget "prompt"   →  bridge.py  →  OpenAI Chat API  →  MCP tools  →  server.py
    │                                                                              │
    └─ ask "prompt"       →  ask.py     →  OpenAI Responses API + vector store    │
                                                                               FastMCP
                                                                               local tools
```

## Components

### `mq-mcp/server.py`

FastMCP server exposing all local tools. Runs as a subprocess via stdio. Entry point:

```bash
uv run mcp run server.py
```

Tools are sandboxed to `REPO_ROOT` (`~/mq-mcp`).

### `mq-mcp/bridge.py`

OpenAI ↔ MCP bridge. Uses Chat Completions API with tool_choice="auto". Spawns server.py as subprocess via `StdioServerParameters`. Handles tool calls in a single round-trip. CLI entry point via `bridget` shell wrapper (`~/bin/bridget`).

### `mq-mcp/ask.py`

Vector store Q&A client. Uses OpenAI Responses API with `file_search` tool against the `mq-mcp-repo-knowledge` vector store. Does NOT use MCP tools — answers from uploaded repo knowledge. Also importable by bridge.py for `--search` routing.

### `mq-mcp/main.py`

Minimal entry point for running the MCP server directly.

### `mq-mcp/mqlaunch.sh`

Interactive TUI launcher for mq-mcp. Cannot be captured by subprocess — always opened in a new Terminal window via osascript.

## Data flow: bridget

1. User runs: `bridget "prompt"`
2. `~/bin/bridget` wrapper `cd`s to project dir, runs `uv run python -u bridge.py "$@"`
3. `bridge.py` spawns `server.py` via stdio MCP protocol
4. `bridge.py` fetches tool catalog from server, injects into system prompt
5. OpenAI decides whether to call a tool
6. If tool call: bridge calls MCP tool, feeds result back to OpenAI
7. Final answer printed with scramble animation as "Bridget: ..."

## Data flow: ask / --search

1. User runs: `ask "prompt"` or `bridget --search "prompt"`
2. `ask.py` calls OpenAI Responses API with `file_search` tool
3. OpenAI searches the vector store `mq-mcp-repo-knowledge`
4. Answer printed with scramble animation as "Bridget: ..."

## Environment

All secrets live in `mq-mcp/.env`, loaded automatically by direnv when `cd`-ing into `~/mq-mcp/mq-mcp`.

Key env vars:

- `OPENAI_API_KEY` — OpenAI API key
- `OPENAI_VECTOR_STORE_ID` — ID of the active vector store (e.g. `vs_6a0513bc1adc8191bc18affe4383d83f`)
- `OPENAI_MODEL` — model override, defaults to `gpt-5.4-mini`
- `MQ_MCP_SERVER_COMMAND` — override MCP server launch command (default: `uv`)
- `MQ_MCP_SERVER_ARGS` — override MCP server args (default: `run mcp run server.py`)

## Shell integration

`~/.zshrc` defines:

- `bridget` — via `~/bin/bridget` wrapper
- `ask()` — shell function running ask.py
- `Ctrl+O` — inserts "bridget " at the prompt
- `mqrepo`, `mqpy`, `mqtest`, `mqval`, `mqstat` — repo shortcuts
- `mqreleasecheck()` — release readiness checks

## Key paths

| Path | Purpose |
|---|---|
| `~/mq-mcp/` | Repo root |
| `~/mq-mcp/mq-mcp/` | Python app (server, bridge, ask) |
| `~/mq-mcp/scripts/` | Build, validate, vector store scripts |
| `~/mq-mcp/docs/` | Documentation |
| `~/mq-mcp/docs/semantic-index/` | AI-optimized semantic index files |
| `~/mq-mcp/tests/` | Pytest test suite |
| `~/bin/bridget` | Shell wrapper for bridge.py |
| `/tmp/mq-mcp-vector-pack/` | Working area for vector store builds |
