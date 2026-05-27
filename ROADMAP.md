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
v0.8.0 — profile templates and client setup polish
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
- tool contract JSON and safety metadata
- mq-agent and mqlaunch integration docs
- packaged `mq-mcp` CLI
- install, upgrade, and uninstall scripts
- health, info, report, and troubleshooting bundle commands
- redacted observability endpoints
- validated MCP profile templates for common clients and workflows

Current priority:

```text
v1.0.0 — stable local MCP platform
```

Reason:

v0.8.0 adds validated profile templates for Claude Desktop, Codex, mq-agent,
OpenAI bridge, repo-only, read-only, developer, and local macOS workflows. The
v1.0.0 adds a machine-readable stability baseline and release evidence for the
full local MCP platform.

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
| v0.2.3  | AI tooling integration                      | Done          |
| v0.3.0  | Usable macOS MCP toolkit                    | Done / verify |
| v0.3.1  | CI, release and validation hardening        | Done          |
| v0.4.0  | Tool contract and safety map v2             | Done          |
| v0.5.0  | mq-agent and mqlaunch integration hardening | Done          |
| v0.6.0  | Packaged local install flow                 | Done          |
| v0.7.0  | Local bridge observability                  | Done          |
| v0.8.0  | Profile templates and client setup polish   | Done          |
| v1.0.0  | Stable local MCP platform                   | Done          |

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

### v0.2.3 — AI tooling integration

Goal:

Wire in mq-image-analyze and Claude Code subagents for richer local
intelligence.

- [x] Bridget face lines dynamically generated via `mq-image-analyze`
- [x] Parallel mq-image analysis with chafa rendering — lower latency
- [x] Fix Bridget face output routing to `/dev/tty` (survives piped contexts)
- [x] Add Claude Code subagents: `mq-project-context`,
  `mcp-tool-safety-reviewer`, `mcp-release-validator`

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

## Completed: v0.3.1 — CI, release and validation hardening

Goal:

Make mq-mcp safe to depend on as the local MCP tool layer for mq-agent,
mqlaunch and future HAL-style workflows.

This release should fix the trust layer before adding more features.

**Scope**

- [x] Fix failing GitHub Actions on `main`
- [x] Ensure `scripts/validate.sh` passes locally
- [x] Ensure `scripts/release-check.sh` passes locally
- [x] Ensure Python syntax checks pass
- [x] Ensure tests pass on supported Python versions
- [x] Ensure docs consistency workflow passes
- [x] Add clear failure output for validation scripts
- [x] Add proof section for current tool count
- [x] Confirm `VERSION`, `pyproject.toml`, README and CHANGELOG are in sync
- [x] Confirm `docs/index.html` reflects the current version
- [x] Confirm `docs/TOOL_SAFETY.md` lists every exposed tool
- [x] Confirm `docs/TOOL_INVENTORY.md` matches actual server tools
- [x] Add a release checklist section for GitHub Actions
- [x] Add branch protection recommendation to docs

**Validation commands**

```bash
uv run python -m py_compile server.py bridge.py
uv run pytest -v
./scripts/validate.sh
./scripts/release-check.sh
```

**Definition of done**

- [x] Latest commit on `main` is green
- [x] GitHub Actions are green
- [x] Local validation passes
- [x] Release check passes
- [x] Tool count is documented once and referenced consistently
- [x] README proof section is current
- [x] CHANGELOG includes v0.3.1
- [x] GitHub release `v0.3.1` exists (shipped as v0.4.0 — merged directly)
- [x] GitHub Pages deployment is successful

---

## v0.4.0 — Tool contract and safety map v2

Goal:

Make every exposed MCP tool self-describing, safe to reason about and easy for
mq-agent to consume.

**Planned scope**

- [x] Add canonical tool contract schema
- [x] Add tool name
- [x] Add tool description
- [x] Add input schema
- [x] Add output schema
- [x] Add safety class
- [x] Add side-effect category
- [x] Add filesystem boundary notes
- [x] Add subprocess behavior notes
- [ ] Add error model
- [ ] Add examples for each tool
- [x] Generate docs from tool metadata
- [x] Add CI check that docs and tool registry match

**Proposed safety classes**

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

**Definition of done**

- [x] Every tool has a declared safety class
- [x] Every tool has a stable metadata entry
- [x] Tool docs are generated or verified from metadata
- [x] CI fails when a tool is undocumented
- [x] mq-agent can consume the tool metadata safely

---

## v0.5.0 — mq-agent and mqlaunch integration hardening

Goal:

Make mq-mcp a reliable backend for mq-agent and mqlaunch workflows.

**Planned scope**

- [x] Verify mq-agent can discover mq-mcp tools
- [x] Verify mq-agent can display mq-mcp tool safety classes
- [x] Verify mq-agent can dry-run mq-mcp tool calls
- [x] Verify mq-agent blocks unsafe tools without approval
- [x] Add docs for mq-agent integration
- [x] Add docs for mqlaunch integration
- [x] Add smoke test for mq-agent → mq-mcp
- [x] Add smoke test for mqlaunch → mq-agent → mq-mcp
- [x] Add example local workflow
- [x] Add troubleshooting for port conflicts and server startup

**Example target flow**

```text
mqlaunch
  ↓
mq-agent
  ↓
mq-mcp
  ↓
safe local tool execution
```

**Possible commands**

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

**Planned scope**

- [x] Add install script
- [x] Add uninstall script
- [x] Add upgrade script
- [x] Add shell completions if useful
- [x] Add launch command
- [x] Add optional background service mode
- [x] Add health check command
- [x] Add local config discovery
- [x] Add example `.env`
- [x] Add docs for clean reinstall

**Possible commands**

```bash
mq-mcp doctor
mq-mcp serve
mq-mcp validate
mq-mcp config path
mq-mcp tools
```

**Non-goals**

- No hidden daemon by default
- No automatic startup without explicit user choice
- No silent credentials handling

---

## v0.7.0 — Local bridge observability

Goal:

Make the MCP server and OpenAI bridge easier to inspect while running.

**Planned scope**

- [x] Add health endpoint
- [x] Add tool count endpoint
- [x] Add server info endpoint
- [x] Add request logging option
- [x] Add redacted debug mode
- [x] Add timing metrics
- [x] Add validation report output
- [x] Add JSON output for diagnostics
- [x] Add troubleshooting bundle command

**Possible commands**

```bash
mq-mcp doctor --json
mq-mcp health
mq-mcp info --json
mq-mcp report --json
mq-mcp report --validate
mq-mcp bundle --validate
```

**Safety requirements**

- Logs must not print secrets
- Debug output must redact tokens and keys
- Local paths should be shown only when useful
- Dangerous tools must remain explicit

---

## v0.8.0 — Profile templates and client setup polish

Goal:

Make mq-mcp easy to connect to different local MCP clients and mq ecosystem
tools.

**Planned scope**

- [x] Add Claude Desktop profile template
- [x] Add Codex profile template
- [x] Add OpenAI bridge profile template
- [x] Add mq-agent profile template
- [x] Add macOS local profile
- [x] Add repo-only profile
- [x] Add read-only profile
- [x] Add developer profile
- [x] Add docs for selecting the right profile
- [x] Add validation for profile files

**Example profiles**

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

- [x] Stable server startup
- [x] Stable tool registry
- [x] Stable tool metadata schema
- [x] Stable safety classes
- [x] Stable filesystem boundary model
- [x] Stable config format
- [x] Stable validation command
- [x] Stable install flow
- [x] Complete tool docs
- [x] Complete troubleshooting docs
- [x] Complete example workflows
- [x] Green CI
- [x] Protected main branch
- [x] GitHub release
- [x] GitHub Pages documentation
- [x] No known critical safety gaps

---

## Review Engine — AI Engineering Runtime

mq-mcp is evolving beyond a local MCP tool layer into a repo-aware engineering
cognition system. The review engine adds structured, contract-driven AI review
directly into the MCP surface.

Strategic principle: better context architecture, not more AI.

---

### Phase 1 — Review Foundation (done)

Goal: make review output consistent, stable, and contract-driven.

- [x] `reviews/contracts/comment-review.md` — hard rules: severity labels,
  output format, scope, max findings, uncertainty handling
- [x] `reviews/skills/python-comment-review.md` — Python-specific guidance:
  docstrings, type hints, naming, module-level side effects
- [x] `reviews/skills/shell-review.md` — shell-specific guidance: headers,
  unquoted vars, silent errors, set -e
- [x] `reviews/skills/mcp-tool-review.md` — MCP tool guidance: Args blocks,
  safety notes, path boundary docs, naming conventions
- [x] `server.py`: `review_file`, `build_repo_context`, `list_review_contracts`
  MCP tools — review engine exposed on the MCP surface (53 tools total)
- [x] Tool docs synced: TOOL_SAFETY.md, TOOL_INDEX.md, README.md,
  tool_contracts.json — all updated to 53 tools
- [x] `reviews/golden/bridge-py-comment-review.md` — 12-finding reference
  review with reasoning notes and excluded-findings section
- [x] `reviews/contracts/architecture-review.md` — ARCHITECTURE and RISK
  severity labels; scoped to boundaries, coupling, doc vs runtime
- [x] `reviews/contracts/security-review.md` — NOTE/WARNING/RISK labels;
  scoped to subprocess injection, path traversal, prompt injection,
  secret leakage, env forwarding, osascript injection

---

### Phase 2 — Repo-Aware Intelligence (in progress)

Goal: give the review engine real system understanding.

- [x] `review_engine/repo_context_builder.py` — generates
  `architecture_map.json` (role of each file) and `file_summary_index.json`
  (public symbols, docstrings, line counts) from file heuristics + Python AST
- [x] `review_engine/review_router.py` — routes files to the correct skill
  by extension and path; wired into `review_file` — skill injected automatically
- [x] `review_engine/severity_engine.py` — parse_findings(), format_summary(),
  has_blocking_findings(), severity_counts(); sorts by severity then line number
- [x] `docs/architecture/SYSTEM_OVERVIEW.md` — ground-truth reference:
  runtime layers, file responsibilities, review pipeline, path safety,
  env vars, tool classes; used for drift detection
- [ ] `docs/architecture/REVIEW_PIPELINE.md`

---

### Phase 3 — Semantic Review Memory (planned)

Goal: intelligent long-term memory for the review engine.

- [ ] Separate review vector store from repo semantic memory
- [ ] Store previous reviews and retrieve similar findings at review time
- [ ] Retrieve coding conventions and architecture notes automatically

---

### Phase 4 — Multi-Pass Review Engine (planned)

Goal: higher quality through structured pipeline.

```text
Pass 1: structure understanding
Pass 2: architecture reasoning
Pass 3: comment/doc review
Pass 4: consistency review
Pass 5: output normalization
```

---

### Phase 5 — Advanced Engineering Review (planned)

- [ ] `--risk` mode: subprocess safety, env leakage, shell injection, MCP exposure
- [ ] Architecture drift detection: README says X, runtime does Y
- [ ] Contract validation: tool contracts, repo boundaries, API assumptions

---

### Phase 6 — Autonomous Review Runtime (planned)

- [ ] Continuous review triggered by `git diff`
- [ ] Review TUI: severity, history, semantic context
- [ ] Agentic review: model selects skill, contract, and generates report automatically

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
Review Engine — Phase 2 completion + Phase 3 start
```

Immediate priorities:

1. `docs/architecture/REVIEW_PIPELINE.md` — document the full review
   pipeline (contract → skill → context → model → severity engine)
2. Add `review_router` skill for `.md` and `.json` files
3. Phase 3: separate review vector store — persist findings across sessions

Keep validating releases with `./scripts/release-check.sh` and only add new
tool surface when safety metadata, tests, profiles, and docs move with it.
