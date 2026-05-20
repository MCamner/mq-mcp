# mq-mcp

[![Validate](https://github.com/MCamner/mq-mcp/actions/workflows/validate.yml/badge.svg)](https://github.com/MCamner/mq-mcp/actions/workflows/validate.yml)
[![Version](https://img.shields.io/badge/version-0.2.1-blue)](https://github.com/MCamner/mq-mcp/releases/tag/0.2.1)

Local MCP server experiments and tooling for macOS.

`mq-mcp` is a small local-first lab for building, testing, and documenting MCP-related workflows on macOS. The goal is to make local MCP setup easier to understand, repeat, validate, and publish safely.

## Status

Early prototype with local MCP tools, validation, and repo-aware helpers.

This repository is currently useful as:

- a local MCP server experiment
- a documentation baseline for MCP setup on macOS
- a place to collect repeatable setup, validation, and troubleshooting flows
- a publishable project shell with README, roadmap, changelog, license, release, and GitHub Pages docs

It is **not yet** a polished package or production-ready MCP distribution.

## What is inside

| Path | Purpose |
| --- | --- |
| `mq-mcp/server.py` | Local FastMCP server experiment |
| `mq-mcp/bridge.py` | Bridge between OpenAI and the local MCP server |
| `mq-mcp/main.py` | Minimal Python entry point |
| `mq-mcp/pyproject.toml` | Python project metadata and dependencies |
| `mq-mcp/.env.example` | Example environment file |
| `docs/index.html` | GitHub Pages landing page |
| `docs/screenshots/` | Place for screenshots and visual docs |
| `CHANGELOG.md` | Release history |
| `ROADMAP.md` | Planned work |
| `VERSION` | Current project version |
| `release.sh` | Local release helper |
| `docs/install.md` | macOS installation guide |

## Quick Start

Clone the repository and enter the Python project folder:

```bash
git clone https://github.com/MCamner/mq-mcp.git
cd mq-mcp/mq-mcp
```

Install dependencies with `uv`:

```bash
uv sync
```

Run the minimal Python entry point:

```bash
uv run python main.py
```

Run the local MCP server experiment:

```bash
uv run mcp run server.py
```

Run the bridge with a prompt:

```bash
uv run python bridge.py "List the available MCP tools."
```

## Requirements

The Python project currently declares:

- Python `>=3.11`
- `mcp[cli]`
- `openai`
- `psutil`
- `pandas`
- `pillow`
- `pyguitarpro`
- `requests`

If your local Python version does not match the project requirement, use `uv` to manage the environment.

## Environment

Copy the example environment file before running anything that needs API credentials (run from inside `mq-mcp/mq-mcp/`):

```bash
cp .env.example .env
```

Do **not** commit real API keys, tokens, private paths, or secrets.

## GitHub Pages

Live docs:

[https://mcamner.github.io/mq-mcp/](https://mcamner.github.io/mq-mcp/)

Current docs include:

- a GitHub Pages landing page
- screenshot folder structure
- public readiness baseline
- macOS installation guide in [`docs/install.md`](docs/install.md)
- MCP client setup guide in [`docs/clients.md`](docs/clients.md)
- MCP server profiles in [`docs/profiles.md`](docs/profiles.md)
- Ghostty terminal setup in [`docs/ghostty.md`](docs/ghostty.md)
- upgrade instructions in [`docs/upgrade.md`](docs/upgrade.md)

## Demo

See [`docs/demo.md`](docs/demo.md) for example commands and expected output.

Quick example — list available tools through the bridge:

```bash
uv --directory mq-mcp run python bridge.py "List the available MCP tools."
```

Expected response lists all 18 MCP tools with descriptions.

## Integration map

See [`docs/integration.md`](docs/integration.md) for how `mq-mcp`, `mq-hal`, and `repo-signal` work together as a local assistant and repo-quality stack.

GitHub Pages version: [integration.html](https://mcamner.github.io/mq-mcp/integration.html)

## Safety notes

See [`docs/security.md`](docs/security.md) for the MCP safety policy.

This project is local-first and experimental.

Before using or extending it:

- review what each MCP tool can access
- avoid committing `.env` files
- keep filesystem access scoped and explicit
- avoid hardcoded machine-specific paths where possible
- prefer read-only tools until validation is solid
- document every command that touches local files or credentials

## Available MCP tools

The local MCP server currently exposes these tools:

- `tool_safety_report` — returns the MCP tool safety classification from docs/TOOL_SAFETY.md
- `hal_repo_report` — runs a read-only mq-hal repo report (audit, brief, release-brief, repo-status, ci)
- `list_local_repos` — lists registered local repositories from MQ_MCP_LOCAL_REPOS
- `open_repo_terminal` — opens a registered local repository in a new Terminal window
- `repo_signal_analyze` — runs repo-signal analyze on a local repository (read-only)
- `repo_signal_checklist` — runs repo-signal publish checklist on a local repository (read-only)
- `get_system_resources` — shows CPU, memory, and disk information
- `read_repo_file` — reads a file inside the repository root
- `list_repo_files` — lists repository files up to a chosen depth
- `search_repo` — searches repository text
- `git_status` — shows branch, working tree status, and recent commits
- `git_diff` — shows current git diff, optionally for one path
- `validate_project` — runs `scripts/validate.sh` when available
- `update_repo_file` — safely replaces exact text in allowed repo files without committing
- `run_mqlaunch` — runs `mqlaunch.sh`
- `analyze_csv` — analyzes CSV files
- `analyze_guitar_pro` — analyzes Guitar Pro files
- `open_in_app` — opens a repo file or explicitly allowed local file in the default app
- `edit_image` — edits an image with supported actions

## Bridget voice

Bridget can optionally speak responses locally on macOS using the built-in `say` command. Disabled by default, no external TTS.

```bash
bridget --voice-list
bridget --voice-name Alva
bridget --voice-on
bridget --voice-test
bridget --voice-off
```

See [`docs/bridget-voice.md`](docs/bridget-voice.md).

## Validation

Run the local validation script from the repository root:

```bash
./scripts/validate.sh
```

The validation checks:

- required project files
- absence of debug and backup files
- Python syntax compilation
- MCP tool listing
- core MCP tools including `read_repo_file`, `list_repo_files`, `search_repo`, `git_status`, `git_diff`, `validate_project`, and `update_repo_file`
- integration documentation wiring
- integration smoke checks for mq-hal and repo-signal MCP tools
- bridge tool discovery checks for the tools Bridget can see through `bridge.py --tools`

You can also run validation through the bridge:

```bash
cd mq-mcp
uv run python bridge.py "Run project validation."
```

## Development checks

Useful local checks:

```bash
git status
python -m compileall mq-mcp/
./scripts/check-bridge-tool-discovery.sh
```

Run the safety tests:

```bash
uv --directory mq-mcp run pytest ../tests -v
```

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned MCP setup, validation, troubleshooting, documentation, and release work.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for solutions to common issues with `uv`, Python versions, and API credentials.

## License

See [LICENSE](LICENSE).
