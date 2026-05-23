# mq-mcp Roadmap

mq-mcp is the local MCP tool layer for the mq ecosystem.

It exposes safe, repo-aware and system-aware tools that can be used by local
agents, OpenAI bridge workflows, mq-agent, mqlaunch and future HAL-style local
automation.

The goal is not to create an unrestricted local automation server.

The goal is to create a controlled, documented and testable MCP surface where
every tool has:

- a clear purpose
- a safety class
- documented inputs
- predictable outputs
- path boundaries
- tests
- failure behavior

---

## Current status

Current project phase:

```text
v0.3.x — usable macOS MCP toolkit
```

Completed foundation:

- local MCP server
- OpenAI/MCP bridge
- repo-scoped file tools
- system resource tools
- git tools
- shell/subprocess safety boundaries
- explicit filesystem allowlist
- Bridget identity asset
- validation script
- docs and GitHub Pages
- tool safety documentation
- tool inventory sync
- Python version documentation cleanup

Current priority:

```text
v0.3.1 — CI, release and validation hardening
```

Reason:

The project is useful enough to become a shared tool layer, so the next step is
to make CI, validation, docs consistency and release checks boringly reliable.

---

## Release map

| Version | Theme                                       | Status        |
| ------- | ------------------------------------------- | ------------- |
| v0.1.0  | Public baseline                             | Done          |
| v0.1.1  | Documentation cleanup                       | Done          |
| v0.1.2  | Local validation flow                       | Done          |
| v0.2.0  | Safer MCP server structure                  | Done          |
| v0.2.1  | Bridget identity + repo metadata sync       | Done          |
| v0.2.2  | Docs sync + tool inventory + CI credibility | Done          |
| v0.3.0  | Usable macOS MCP toolkit                    | Done / verify |
| v0.3.1  | CI, release and validation hardening        | Next          |
| v0.4.0  | Tool contract and safety map v2             | Planned       |
| v0.5.0  | mq-agent and mqlaunch integration hardening | Planned       |
| v0.6.0  | Packaged local install flow                 | Planned       |
| v0.7.0  | Local bridge observability                  | Planned       |
| v0.8.0  | Profile templates and client setup polish   | Planned       |
| v1.0.0  | Stable local MCP platform                   | Future        |

---

## Completed

### v0.1.0 — Public baseline

- [x] Create repository
- [x] Add README
- [x] Add LICENSE
- [x] Add CHANGELOG
- [x] Add VERSION
- [x] Add ROADMAP
- [x] Add GitHub Pages docs folder
- [x] Add docs/index.html
- [x] Add docs/screenshots/
- [x] Add issue templates
- [x] Add first release

---

### v0.1.1 — Documentation cleanup

Goal:

Make the project understandable from the GitHub front page.

- [x] Fix root README formatting
- [x] Explain what the project is and is not
- [x] Document the repository layout
- [x] Document the local setup flow
- [x] Document how to run the MCP server
- [x] Document how to run the OpenAI/MCP bridge
- [x] Add clear safety notes
- [x] Add basic development checks
- [x] Confirm GitHub Pages link works
- [x] Add terminal output example

---

### v0.1.2 — Local validation flow

Goal:

Make it easy to verify that the local MCP setup works.

- [x] Add a simple validation command
- [x] Add expected output examples
- [x] Add troubleshooting notes for missing `uv`
- [x] Add troubleshooting notes for Python version mismatch
- [x] Add troubleshooting notes for missing OpenAI credentials
- [x] Add troubleshooting notes for MCP server startup failures
- [x] Add a smoke-test script
- [x] Add a release-readiness checklist

---

### v0.2.0 — Safer MCP server structure

Goal:

Make the local MCP server safer and easier to extend.

- [x] Replace hardcoded local paths with config or environment variables
- [x] Add an explicit filesystem allowlist
- [x] Document every exposed MCP tool
- [x] Separate system tools from repo/file tools
- [x] Add safer error handling
- [x] Add tests for path safety
- [x] Add tests for tool output shape
- [x] Add a minimal example config file

---

### v0.2.1 — Bridget identity + repo metadata sync

Goal:

Give the project a recognizable identity and improve repo metadata quality.

- [x] Add Python syntax check workflow
- [x] Add basic test workflow
- [x] Add status badge when CI exists
- [x] Add Bridget face identity asset
- [x] Add Bridget face trigger to `bridge.py`
- [x] Add Bridget smoke-check to `scripts/validate.sh`
- [x] Sync `pyproject.toml` version with `VERSION`
- [x] Migrate unsafe `os.path.normpath` paths in `server.py`
- [x] Update GitHub Pages landing page

---

### v0.2.2 — Docs sync + tool inventory + CI credibility

Goal:

Make the repository trustworthy by removing stale documentation and tool count
drift.

- [x] Sync tool count across README, demo docs and safety docs
- [x] Fix Python version requirement in docs
- [x] Update stale tool list
- [x] Add proof section to README
- [x] Add `scripts/release-check.sh`
- [x] Add docs consistency workflow
- [x] Add tool inventory docs
- [x] Improve CI credibility

---

### v0.3.0 — Usable macOS MCP toolkit

Goal:

Make mq-mcp useful beyond a one-off local experiment.

- [x] Add a stable launcher command
- [x] Add documented MCP server profiles
- [x] Add setup examples for common MCP clients
- [x] Add screenshots for installation and usage
- [x] Add a complete troubleshooting page
- [x] Add example workflows
- [x] Add clear upgrade instructions
- [x] Make tool documentation easier to follow
- [x] Make validation flow repeatable

---

## Next: v0.3.1 — CI, release and validation hardening

Goal:

Make mq-mcp safe to depend on as the local MCP tool layer for mq-agent,
mqlaunch and future HAL-style workflows.

This release should fix the trust layer before adding more features.

### Scope

- [ ] Fix failing GitHub Actions on `main`
- [ ] Ensure `scripts/validate.sh` passes locally
- [ ] Ensure `scripts/release-check.sh` passes locally
- [ ] Ensure Python syntax checks pass
- [ ] Ensure tests pass on supported Python versions
- [ ] Ensure docs consistency workflow passes
- [ ] Add clear failure output for validation scripts
- [ ] Add proof section for current tool count
- [ ] Confirm `VERSION`, `pyproject.toml`, README and CHANGELOG are in sync
- [ ] Confirm `docs/index.html` reflects the current version
- [ ] Confirm `docs/TOOL_SAFETY.md` lists every exposed tool
- [ ] Confirm `docs/TOOL_INVENTORY.md` matches actual server tools
- [ ] Add a release checklist section for GitHub Actions
- [ ] Add branch protection recommendation to docs

### Validation commands

```bash
uv run python -m py_compile server.py bridge.py
uv run pytest -v
./scripts/validate.sh
./scripts/release-check.sh
```

### Definition of done

- [ ] Latest commit on `main` is green
- [ ] GitHub Actions are green
- [ ] Local validation passes
- [ ] Release check passes
- [ ] Tool count is documented once and referenced consistently
- [ ] README proof section is current
- [ ] CHANGELOG includes v0.3.1
- [ ] GitHub release `v0.3.1` exists
- [ ] GitHub Pages deployment is successful

---

## v0.4.0 — Tool contract and safety map v2

Goal:

Make every exposed MCP tool self-describing, safe to reason about and easy for
mq-agent to consume.

### Planned scope

- [ ] Add canonical tool contract schema
- [ ] Add tool name
- [ ] Add tool description
- [ ] Add input schema
- [ ] Add output schema
- [ ] Add safety class
- [ ] Add side-effect category
- [ ] Add filesystem boundary notes
- [ ] Add subprocess behavior notes
- [ ] Add error model
- [ ] Add examples for each tool
- [ ] Generate docs from tool metadata
- [ ] Add CI check that docs and tool registry match

### Proposed safety classes

```text
read-only
repo-read
repo-write
local-file-read
local-file-write
subprocess
external-app
dangerous
unknown
```

### Definition of done

- [ ] Every tool has a declared safety class
- [ ] Every tool has a stable metadata entry
- [ ] Tool docs are generated or verified from metadata
- [ ] CI fails when a tool is undocumented
- [ ] mq-agent can consume the tool metadata safely

---

## v0.5.0 — mq-agent and mqlaunch integration hardening

Goal:

Make mq-mcp a reliable backend for mq-agent and mqlaunch workflows.

### Planned scope

- [ ] Verify mq-agent can discover mq-mcp tools
- [ ] Verify mq-agent can display mq-mcp tool safety classes
- [ ] Verify mq-agent can dry-run mq-mcp tool calls
- [ ] Verify mq-agent blocks unsafe tools without approval
- [ ] Add docs for mq-agent integration
- [ ] Add docs for mqlaunch integration
- [ ] Add smoke test for mq-agent → mq-mcp
- [ ] Add smoke test for mqlaunch → mq-agent → mq-mcp
- [ ] Add example local workflow
- [ ] Add troubleshooting for port conflicts and server startup

### Example target flow

```text
mqlaunch
  ↓
mq-agent
  ↓
mq-mcp
  ↓
safe local tool execution
```

### Possible commands

```bash
mq-agent mcp status
mq-agent mcp tools
mq-agent run-tool read_repo_file --arg path=README.md --dry-run
mqlaunch agent mcp-status
mqlaunch agent mcp-tools
```

---

## v0.6.0 — Packaged local install flow

Goal:

Make mq-mcp easy to install, update and run on a new macOS machine.

### Planned scope

- [ ] Add install script
- [ ] Add uninstall script
- [ ] Add upgrade script
- [ ] Add shell completions if useful
- [ ] Add launch command
- [ ] Add optional background service mode
- [ ] Add health check command
- [ ] Add local config discovery
- [ ] Add example `.env`
- [ ] Add docs for clean reinstall

### Possible commands

```bash
mq-mcp doctor
mq-mcp serve
mq-mcp validate
mq-mcp config path
mq-mcp tools
```

### Non-goals

- No hidden daemon by default
- No automatic startup without explicit user choice
- No silent credentials handling

---

## v0.7.0 — Local bridge observability

Goal:

Make the MCP server and OpenAI bridge easier to inspect while running.

### Planned scope

- [ ] Add health endpoint
- [ ] Add tool count endpoint
- [ ] Add server info endpoint
- [ ] Add request logging option
- [ ] Add redacted debug mode
- [ ] Add timing metrics
- [ ] Add validation report output
- [ ] Add JSON output for diagnostics
- [ ] Add troubleshooting bundle command

### Possible commands

```bash
mq-mcp doctor --json
mq-mcp health
mq-mcp report
```

### Safety requirements

- Logs must not print secrets
- Debug output must redact tokens and keys
- Local paths should be shown only when useful
- Dangerous tools must remain explicit

---

## v0.8.0 — Profile templates and client setup polish

Goal:

Make mq-mcp easy to connect to different local MCP clients and mq ecosystem
tools.

### Planned scope

- [ ] Add Claude Desktop profile template
- [ ] Add Codex profile template
- [ ] Add OpenAI bridge profile template
- [ ] Add mq-agent profile template
- [ ] Add macOS local profile
- [ ] Add repo-only profile
- [ ] Add read-only profile
- [ ] Add developer profile
- [ ] Add docs for selecting the right profile
- [ ] Add validation for profile files

### Example profiles

```text
profiles/read-only.json
profiles/repo-dev.json
profiles/local-macos.json
profiles/mq-agent.json
profiles/openai-bridge.json
```

---

## v1.0.0 — Stable local MCP platform

Goal:

Make mq-mcp stable enough to be the default MCP tool layer for the mq ecosystem.

### v1.0.0 requirements

- [ ] Stable server startup
- [ ] Stable tool registry
- [ ] Stable tool metadata schema
- [ ] Stable safety classes
- [ ] Stable filesystem boundary model
- [ ] Stable config format
- [ ] Stable validation command
- [ ] Stable install flow
- [ ] Complete tool docs
- [ ] Complete troubleshooting docs
- [ ] Complete example workflows
- [ ] Green CI
- [ ] Protected main branch
- [ ] GitHub release
- [ ] GitHub Pages documentation
- [ ] No known critical safety gaps

---

## Long-term ideas

These are intentionally not scheduled yet.

- Bridget voice mode
- Bridget terminal avatar mode
- richer local TUI
- local model fallback
- Ollama integration
- local event history
- repo health history
- MCP tool marketplace
- integration with mq-hal
- integration with mq-ums
- integration with repo-signal semantic memory
- cross-repo tool inventory
- visual safety map
- generated architecture diagrams
- demo videos or GIFs

---

## Design principles

mq-mcp should remain:

- local-first
- explicit
- safe by default
- repo-aware
- path-bounded
- testable
- observable
- easy to validate
- easy to disable
- useful without hidden automation

The server should expose tools.

It should not become an unrestricted remote-control layer.

---

## Safety principles

mq-mcp must never:

- expose arbitrary filesystem access by default
- run subprocess tools silently
- ignore path boundaries
- leak API keys
- print secrets in logs
- mutate repositories without explicit tool intent
- hide dangerous behavior behind friendly names
- treat AI-generated requests as automatically trusted

Every powerful tool must have:

- a safety class
- documented inputs
- documented outputs
- tests
- error handling
- explicit approval behavior when used by higher-level agents

---

## Current recommended next step

Work on:

```text
v0.3.1 — CI, release and validation hardening
```

This release should make the project boringly reliable before adding more tool
surface or deeper mq-agent integration.
