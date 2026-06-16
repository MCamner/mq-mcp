# mq-mcp

[![Validate](https://github.com/MCamner/mq-mcp/actions/workflows/validate.yml/badge.svg)](https://github.com/MCamner/mq-mcp/actions/workflows/validate.yml)
[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/MCamner/mq-mcp/releases/tag/v2.0.0)

Local MCP server experiments and tooling for macOS.

`mq-mcp` is a small local-first lab for building, testing, and documenting MCP-related workflows on macOS. The goal is to make local MCP setup easier to understand, repeat, validate, and publish safely.

In the MQ stack, `mq-mcp` is the execution runtime: it exposes bounded tools,
safety metadata, review, memory, and bridge calls. Planning, routing, dry-runs,
and approval UX belong in `mq-agent`; repo health scoring belongs in
`repo-signal`; operator reports belong in `mq-hal`.

## Status

v2.0.0 — Release Gate v2 + deterministic readiness: lint/type, contract-drift, unsafe-command, and read-only perception-review checks complete the deterministic release gate, on top of the brain/Obsidian tools, local Ollama learn provider, and mq-agent learn compatibility aliases.

This repository is useful as:

* a local MCP server with 125 documented, safety-classified tools
* a packaged local CLI with `mq-mcp doctor`, `mq-mcp health`, `mq-mcp report`, `mq-mcp serve`, `mq-mcp validate`, and `mq-mcp tools`
* validated MCP profile templates for Claude Desktop, Codex, mq-agent, OpenAI bridge, and local macOS workflows
* a v1 stability baseline with `mq-mcp stability validate` and `docs/stability.json`
* a validation baseline with `scripts/validate.sh` and `scripts/release-check.sh`
* a repo-aware and macOS-aware MCP surface for mq-agent and local workflows
* a documented integration point for mq-hal and repo-signal
* an optional local-first Ollama learn extraction policy where mq-mcp remains
  the source of truth for validation, safety, and memory

It is **not yet** a production-ready MCP distribution or hidden daemon.

## Proof

* Python files compile in CI (`python -m compileall mq-mcp/`)
* `scripts/validate.sh` runs on every push — checks required files, Python syntax, MCP tool listing, and integration wiring
* Path access is scoped through `resolve_repo_file()` and `resolve_allowed_local_file()` — no arbitrary filesystem access
* Write-capable tools (`update_repo_file`, `edit_image`) never commit automatically
* Safety policy classifies all 125 tools by class, resolver, write capability, and subprocess use — see `docs/TOOL_SAFETY.md`
* Tests for path safety and tool output shape run in CI via `pytest`
* CI runs on `macos-latest` — not a Linux approximation

## What is inside

| Path | Purpose |
| --- | --- |
| `mq-mcp/server.py` | Local FastMCP server experiment |
| `mq-mcp/bridge.py` | Bridge between OpenAI and the local MCP server |
| `mq-mcp/main.py` | Minimal Python entry point |
| `mq-mcp/pyproject.toml` | Python project metadata and dependencies |
| `mq-mcp/.env.example` | Example environment file |
| `scripts/install.sh` | Local install helper for dependencies, `.env`, and the `mq-mcp` command |
| `scripts/upgrade.sh` | Safe update helper for pull, sync, reinstall, and validation |
| `scripts/uninstall.sh` | Local CLI uninstall helper |
| `completions/_mq-mcp` | Optional zsh completions |
| `profiles/` | Versioned MCP profile templates for clients and workflows |
| `docs/stability.json` | Machine-readable v1 stability baseline |
| `docs/index.html` | GitHub Pages landing page |
| `docs/screenshots/` | Place for screenshots and visual docs |
| `CHANGELOG.md` | Release history |
| `ROADMAP.md` | Planned work |
| `VERSION` | Current project version |
| `release.sh` | Local release helper |
| `docs/install.md` | macOS installation guide |

## Quick Start

Clone the repository and run the local installer:

```bash
git clone https://github.com/MCamner/mq-mcp.git
cd mq-mcp
./scripts/install.sh
```

Check the local install:

```bash
mq-mcp doctor
mq-mcp health
mq-mcp tools
mq-mcp profiles list
mq-mcp stability validate
```

Run the local MCP server experiment:

```bash
mq-mcp serve
```

Run validation:

```bash
mq-mcp validate
```

Write a redacted troubleshooting bundle:

```bash
mq-mcp report --json
mq-mcp bundle --validate
```

Run the bridge with a prompt:

```bash
cd mq-mcp
uv run python bridge.py "List the available MCP tools."
```

## Requirements

The Python project currently declares:

* Python `>=3.11`
* `mcp[cli]`
* `openai`
* `psutil`
* `pandas`
* `pillow`
* `pyguitarpro`
* `requests`

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

* a GitHub Pages landing page
* screenshot folder structure
* public readiness baseline
* macOS installation guide in [`docs/install.md`](docs/install.md)
* packaged local install, upgrade, uninstall, and clean reinstall commands
* redacted observability commands and HTTP endpoints for local diagnostics
* MCP client setup guide in [`docs/clients.md`](docs/clients.md)
* MCP server profiles in [`docs/profiles.md`](docs/profiles.md)
* v1 stability baseline in [`docs/stability.md`](docs/stability.md)
* Ghostty terminal setup in [`docs/ghostty.md`](docs/ghostty.md)
* upgrade instructions in [`docs/upgrade.md`](docs/upgrade.md)

## Demo

See [`docs/demo.md`](docs/demo.md) for example commands and expected output.

Quick example — list available tools through the bridge:

```bash
uv --directory mq-mcp run python bridge.py "List the available MCP tools."
```

Expected response lists all 125 MCP tools with descriptions.

## Integration map

See [`docs/integration.md`](docs/integration.md) for how `mq-mcp`, `mq-hal`, and `repo-signal` work together as a local assistant and repo-quality stack.

See [`docs/orchestration-boundary.md`](docs/orchestration-boundary.md) for the
practical boundary between `mq-mcp`, `mq-agent`, `mq-hal`, `repo-signal`, and
`mq-image-analyze`.

See [`docs/LEARN_OLLAMA.md`](docs/LEARN_OLLAMA.md) for the optional
Ollama-backed learn extraction policy. Ollama may be used only for local pattern
extraction; mq-mcp owns the learn contract, validation, safety classes, review
logic, and memory writes.

GitHub Pages version: [integration.html](https://mcamner.github.io/mq-mcp/integration.html)

## Ecosystem

`mq-mcp` is the execution runtime in the MQ ecosystem — it exposes tools and enforces safety boundaries. It does not plan or orchestrate.

| Repo               | Use when you need to…                                                  |
|--------------------|------------------------------------------------------------------------|
| `mq-mcp`           | Execute a tool, run a review, read a file, check safety metadata       |
| `mq-agent`         | Plan a multi-step workflow or route a request across repos             |
| `mq-hal`           | Get a system status report, release brief, or operator summary         |
| `repo-signal`      | Score a repo's publish readiness or run a documentation quality check  |
| `mq-image-analyze` | Analyze a screenshot, diagram, or visual render                        |

**Which tools run automatically (no approval needed):** Class A and B — all read-only tools. Examples: `read_repo_file`, `git_status`, `repo_signal_analyze`, `get_system_resources`.

**Which tools require explicit human approval:** Class C (writes files) and Class D (opens apps or runs subprocesses). Examples: `update_repo_file`, `run_tests`, `open_terminal`, `set_reminder`.

See [`docs/orchestration-boundary.md`](docs/orchestration-boundary.md) for the full boundary definition and profile-to-class mapping.

## Safety notes

See [`docs/security.md`](docs/security.md) for the MCP safety policy.
See [`docs/TOOL_SAFETY.md`](docs/TOOL_SAFETY.md) for the full tool class map.

This project is local-first and experimental.

Before using or extending it:

* review what each MCP tool can access
* avoid committing `.env` files
* keep filesystem access scoped and explicit
* avoid hardcoded machine-specific paths where possible
* prefer read-only tools until validation is solid
* document every command that touches local files or credentials

Automation rule of thumb:

* Class A/B tools may be used automatically when the caller accepts the
  documented read-only or external-access behavior.
* Class C/D tools require an explicit human approval gate because they write
  files, open apps, or run subprocesses.
* Review tools should be treated as explicit review actions when they call
  OpenAI, even if their local filesystem behavior is read-only.

## Available MCP tools

The local MCP server exposes 125 tools across five safety classes. See [`docs/TOOL_SAFETY.md`](docs/TOOL_SAFETY.md) for the full classification.

**Repo tools (Class A — read-only, repo-scoped):**

* `read_repo_file` — reads a file inside the repository root
* `list_repo_files` — lists repository files up to a chosen depth
* `release_gate_run` — runs Release Gate v2 deterministic release validation
* `search_repo` — searches repository text
* `git_status` — shows branch, working tree status, and recent commits
* `git_diff` — shows current git diff, optionally for one path
* `analyze_csv` — analyzes CSV files inside the repo
* `tool_safety_report` — returns the MCP tool safety classification from docs/TOOL_SAFETY.md
* `shell_exec` — runs an arbitrary shell command (Class D); disabled unless `MQ_MCP_ALLOW_SHELL_EXEC=1`, which the bridge sets only in `--do` mode behind a y/n approval gate
* `list_local_repos` — lists registered local repositories from MQ_MCP_LOCAL_REPOS
* `list_openable_apps` — returns static list of apps Bridget can open or control

**System read (Class B — read-only, external access):**

* `get_system_resources` — shows CPU, memory, and disk information
* `analyze_guitar_pro` — analyzes Guitar Pro files in repo or allowed roots
* `repo_signal_analyze` — runs repo-signal analyze on a local repository (read-only)
* `repo_signal_checklist` — runs repo-signal publish checklist on a local repository (read-only)
* `repo_signal_inspect` — runs repo-signal inspect --json and returns structured inspect.v1 data
* `repo_signal_doctor_json` — runs repo-signal doctor --json and returns structured doctor.v1 data
* `repo_signal_report` — runs repo-signal report --format json and returns structured report.v1 data
* `repo_signal_suggest` — runs repo-signal suggest --format json and returns structured suggest.v1 data
* `repo_signal_positioning` — runs repo-signal positioning --json and returns structured positioning.v1 data
* `repo_signal_status` — reports whether repo-signal export packs are present and merged (Class A, read-only)
* `zephyr_validate` — validates a zephyr architecture YAML file
* `zephyr_review` — reviews a zephyr architecture YAML file
* `zephyr_analyze` — analyzes a zephyr architecture YAML file
* `zephyr_diff` — compares two zephyr architecture YAML files
* `image_observe_architecture` — observes an architecture diagram through mq-image
* `image_analyze_ui` — analyzes a UI screenshot through mq-image
* `image_analyze` — analyzes an image through mq-image
* `ums_command_catalog` — reads the mq-ums command catalog from MQ_UMS_DIR/config
* `ums_audit_log` — reads mq-ums local audit logs from MQ_UMS_DIR/logs
* `get_clipboard` — reads the current macOS clipboard
* `get_wifi_info` — returns current Wi-Fi network name and signal info
* `get_battery_status` — returns battery level, charging state, and estimated time remaining
* `list_running_apps` — lists all visible macOS applications currently running
* `get_todays_events` — returns today's events from Calendar.app
* `find_large_files` — finds files larger than a given size in a directory
* `find_recent_files` — finds files modified within the last N days
* `check_port` — checks whether a TCP port is in use on localhost
* `get_public_ip` — returns the current public IP address

**Write-capable (Class C — controlled scope):**

* `update_repo_file` — safely replaces exact text in allowed repo files without committing
* `edit_image` — edits an image with supported actions (rotate, grayscale)
* `set_clipboard` — copies text to the macOS clipboard
* `take_screenshot` — captures the screen and saves to a file

**Subprocess / open-app (Class D):**

* `open_in_app` — opens a repo file or explicitly allowed local file in the default app
* `validate_project` — runs `scripts/validate.sh` when available
* `run_mqlaunch` — runs `mqlaunch.sh`
* `open_repo_terminal` — opens a registered local repository in a new Terminal window
* `hal_repo_report` — runs a read-only mq-hal repo report (audit, brief, release-brief, repo-status, ci)
* `open_messages` — opens Messages.app, optionally to a contact
* `open_finder` — opens Finder at a given path
* `open_url` — opens a URL in the default browser
* `show_notification` — sends a macOS system notification
* `open_app` — launches any macOS application by name
* `speak_text` — speaks text aloud via macOS text-to-speech
* `open_chrome` — opens Google Chrome, optionally to a URL
* `open_spotify` — opens Spotify, optionally to a track, album, or search
* `open_terminal` — opens a new Terminal window, optionally at a path
* `open_vscode` — opens VS Code, optionally at a file or folder
* `set_volume` — sets the macOS system output volume
* `toggle_dark_mode` — toggles macOS between dark mode and light mode
* `lock_screen` — locks the macOS screen immediately
* `create_note` — creates a new note in Notes.app
* `set_reminder` — creates a reminder in Reminders.app
* `set_wallpaper` — sets the macOS desktop wallpaper
* `run_tests` — runs pytest in a registered local repository
* `run_mqlaunch_doctor` — runs `mqlaunch doctor` (structured PASS/FAIL health report)
* `run_mqlaunch_selftest` — runs `mqlaunch selftest` (internal smoke checks)
* `run_mqlaunch_release_check` — runs `mqlaunch release-check` (pre-release gate)
* `run_mqlaunch_version` — runs `mqlaunch version` (TUI output; version extracted heuristically)
* `run_mqlaunch_system_check` — runs `mqlaunch system check` (TUI; structured data not available headless)
* `run_mqlaunch_perf` — runs `mqlaunch perf` (TUI menu; no parseable output headless)
* `run_mqlaunch_demo` — runs `mqlaunch demo` (interactive TUI; no output headless)
* `run_mqlaunch_bundle` — runs `mqlaunch bundle` (TUI; bundle NOT created headless)
* `run_mqlaunch_ask` — asks mqlaunch a natural-language question (requires OPENAI_API_KEY)

**Learn layer tools (Class A/C):**

* `record_learning` — stores a verified engineering lesson locally with secret redaction (Class C, writes lessons.jsonl)
* `learn_from_review` — creates a learning record from the last review findings for a file (Class C)
* `learn_from_diff` — creates a learning record with current git diff as context (Class C)
* `bootstrap_learning_memory` — seeds the learn layer from architecture memory ADRs (Class C)
* `list_learnings` — lists stored lessons with optional repo/source/risk filters (Class A)
* `get_learning` — returns a single lesson by id prefix (Class A)
* `explain_learned_pattern` — mq-agent-compatible alias for `get_learning` (Class A)
* `search_learnings` — full-text search across lessons (Class A)
* `search_learned_patterns` — mq-agent-compatible alias for `search_learnings` (Class A)
* `summarize_learnings` — summarizes lessons by source and risk (Class A)
* `learn_hygiene` — reports learn memory hygiene: duplicates, invalid records, low-confidence storage, and missing validation (Class A)
* `learning_status` — returns learn layer stats: counts by source, risk, and repo (Class A)
* `learn_status` — mq-agent-compatible alias for `learning_status` (Class A)
* `learn_inbox` — lists pending learn candidates auto-extracted from commits by the post-commit hook, awaiting review (Class A)
* `learn_inbox_drop` — removes exactly one pending candidate from the inbox after promotion/skip; previews by default, `apply=True` to remove; never touches the curated store (Class C)
* `learn_inbox_draft` — maps one inbox candidate to a review-ready `record_learning` draft (task/lesson/validation/risk/repo/source/tags); preview-only, writes nothing, validation is always a MANUAL VALIDATION REQUIRED instruction so promotion stays a human decision (Class A)
* `ollama_learn_status` — reports whether the local Ollama server is running and the mq-learn model is installed; read-only (Class B)
* `ollama_learn_extract` — dry-run extraction of a learn pattern from review findings via local Ollama; no storage, preview only (Class B)
* `learn_extract_from_last_review` — loads stored review findings for a file, runs dry-run Ollama extraction, returns a preview candidate; no storage (Class B)
* `promote_learning` — previews how a lesson would appear in a target doc, no file writes (Class A)

**Brain tools (Class A/C):**

* `brain_status` — reports mqobsidian vault availability and top-level folders (Class A)
* `brain_record_decision` — writes an ADR to mqobsidian/decisions/ (Class C)
* `brain_record_review` — writes a review summary to mqobsidian/reviews/ (Class C)
* `brain_record_session` — writes a session note to mqobsidian/sessions/ (Class C)
* `brain_record_learning` — writes a learned pattern to mqobsidian/learn/ (Class C)
* `brain_promote_learning` — promotes a learning note into mqobsidian/learn/verified/ (Class C)

**Review engine tools:**

* `review_file` — runs an AI review on a repo file using a review contract (requires OPENAI_API_KEY)
* `risk_review_file` — targeted risk pass (security/risk/architecture) with grep pre-scan + AI review (requires OPENAI_API_KEY)
* `risk_review_diff` — risk pass over changed files in the working tree or staging area (requires OPENAI_API_KEY)
* `build_repo_context` — rebuilds architecture_map.json and file_summary_index.json for the review engine
* `list_review_contracts` — lists available review contracts and their modes
* `list_review_skills` — lists available review skills with path-prefix routes, extension routes, and availability status (Class A)
* `list_review_history` — lists all files with review history and last review summary
* `get_last_review` — returns the most recent review findings for a repo file from local memory
* `detect_architecture_drift` — detects drift between declared documentation and actual runtime state
* `review_runtime_contract` — verifies RUNTIME_CONTRACT.md claims against actual server state; structural checks + optional AI architecture pass
* `validate_orchestration_contract` — verifies tool set satisfies the orchestration contract: profiles, safety classes, error prefixes (Class A, no API key)
* `list_architecture_docs` — lists docs/architecture/ with freshness status relative to server.py
* `review_architecture_doc` — applies architecture review contract to a named architecture document with injected runtime state
* `list_architecture_decisions` — lists all architecture memory entries (ADRs, boundaries, philosophy, rejected patterns)
* `get_architecture_decision` — returns the full text of a specific architecture memory entry by ID
* `record_architecture_decision` — records a new ADR in architecture_memory/ (Class C, writes file, does not commit)
* `extract_coding_conventions` — extracts generalizable conventions from the last review of a file and persists them to architecture_memory/ (Class C, requires OPENAI_API_KEY)
* `store_semantic_memory` — stores or updates a knowledge item in semantic memory (Class C, writes semantic_memory/store.json)
* `search_semantic_memory` — keyword search across semantic memory keys, tags, and content (Class A)
* `get_semantic_memory` — returns the full content of a semantic memory item by key (Class A)
* `list_semantic_memory` — lists all semantic memory items with previews (Class A)
* `bootstrap_semantic_memory` — ingests README, ROADMAP, RUNTIME_CONTRACT.md, ORCHESTRATION_CONTRACT.md, TOOL_SAFETY.md into semantic memory (Class C)
* `export_symbol_index` — writes a callgraph symbol map to generated/symbols/symbol_index.json (Class C)
* `review_diff` — reviews all git-changed files using the configured review mode (requires OPENAI_API_KEY)
* `review_repo` — reviews the least-recently-reviewed repo files (requires OPENAI_API_KEY)

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

* required project files
* absence of debug and backup files
* Python syntax compilation
* MCP tool listing
* core MCP tools including `read_repo_file`, `list_repo_files`, `search_repo`, `git_status`, `git_diff`, `validate_project`, and `update_repo_file`
* integration documentation wiring
* integration smoke checks for mq-hal and repo-signal MCP tools
* bridge tool discovery checks for the tools Bridget can see through `bridge.py --tools`

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
