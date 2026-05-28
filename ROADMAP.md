# mq-mcp Roadmap

mq-mcp is a **local deterministic AI execution runtime for engineering workflows**.

The real strategic category is **local engineering cognition runtime** — not
"MCP server" or "tool collection". The distinction matters: a tool collection
grows by adding tools. An engineering cognition runtime grows by improving the
quality of context, structure, and symbolic understanding it brings to every
tool call.

It is not a chatbot, agent framework, or autonomous system. It exposes a
controlled, documented, and testable MCP surface where every tool has a declared
safety class, path boundary, and predictable output shape.

The goal is not to create an unrestricted local automation server.

The goal is to create a system that is:

- self-describing — the runtime can explain its own boundaries
- verifiable — contracts are enforced and drift is detected
- self-reflective — the runtime can review and diagnose itself
- deterministic — same inputs, same output structure, always
- symbolically aware — the runtime understands structure, not just content

**The highest-leverage improvement at any phase is context quality, not more
features.** All real quality gains come from giving the model better structured
knowledge of the system it is reasoning about.

Authoritative identity contract: `docs/RUNTIME_CONTRACT.md`

---

## Current status

Current project phase:

```text
v1.0.0 — stable local MCP platform (done)
Next:    Runtime Consolidation — self-describing, self-reviewing runtime
```

Completed foundation:

- local MCP server with 58 tools across safety classes A–D
- OpenAI/MCP bridge
- repo-scoped file tools with path boundary enforcement
- system resource tools
- git tools
- shell/subprocess safety boundaries
- explicit filesystem allowlist
- Bridget identity asset
- validation and release-check scripts
- docs and GitHub Pages
- tool safety documentation and tool inventory sync
- tool contract JSON and safety metadata (`docs/tool_contracts.json`)
- mq-agent and mqlaunch integration docs
- packaged `mq-mcp` CLI
- install, upgrade, and uninstall scripts
- health, info, report, and troubleshooting bundle commands
- redacted observability endpoints
- validated MCP profile templates for common clients and workflows
- Review engine: contracts, skills, severity engine, review memory, multi-pass
  reviewer, drift detector, `review_diff`, `review_repo`
- `docs/RUNTIME_CONTRACT.md` — authoritative identity and execution contract

---

## Ecosystem position

```text
mq-agent          — orchestration layer (consumes mq-mcp as runtime)
mq-mcp            — deterministic execution runtime  ← this repo
repo-signal       — repository intelligence (read-only analysis)
mq-hal            — operator interface layer
mq-image-analyze  — vision layer (invoked as a tool)
atlas-one         — prompt and interaction layer
macos-scripts     — human terminal UX and launch surface
```

This layering is not aspirational — it is enforced by the architecture.
mq-mcp executes. mq-agent orchestrates. The boundary must not blur.

### Cross-repo responsibility contract

mq-mcp owns the central cognition runtime:

- review engine and review contracts
- semantic retrieval and review memory
- repo context selection for reviews
- architecture memory and architecture drift detection
- MCP runtime and safety metadata
- multi-pass review and risk analysis

mq-mcp must not absorb heavy UI, duplicated repository indexing, repo metrics
dashboards, or workflow automation logic. Those belong to mq-agent,
repo-signal, macos-scripts and mq-hal.

---

## System feedback loops

The most valuable loop in the system:

```text
Better contracts
→ better review
→ better self-understanding
→ better runtime stability
→ better contracts
```

The self-review loop:

```text
mq-mcp reviews itself
→ finds drift
→ improves contracts
→ improves next review
```

When this loop is closed, the runtime acquires:

- self-diagnostics
- architectural immune response
- adaptive stabilization

The permanent design tension:

```text
More AI flexibility → more emergent behavior → more contracts needed → less flexibility
```

This is not a problem to solve. It is a tension to design.

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
| v1.1.0  | Runtime self-inspection                     | Done          |
| v1.2.0  | Architecture memory                         | Done          |
| v1.3.0  | Orchestration boundary formalization        | Done          |
| v1.4.0  | Semantic memory layer                       | Planned       |
| v1.5.0  | Risk analysis layer                         | Planned       |
| v1.6.0  | Generated artifacts + repo-signal merge     | Planned       |

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

### Phase 2 — Repo-Aware Intelligence (done)

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
- [x] `docs/architecture/REVIEW_PIPELINE.md` — full pipeline reference:
  stages, prompt structure, severity parsing, memory persistence, MCP tools
- [x] `review_engine/callgraph_builder.py` — cross-file import graph and hub
  file detection. Outputs `review_engine/context/callgraph.json` with
  `imports`, `importers`, `hub_files`, `symbols`, and `edges`. Wired into
  `build_repo_context` (regenerated alongside architecture_map.json) and
  `review_file` / `MultiPassReviewer.review_pass` — cross-file context injected
  for every file, with hub files and their importers named explicitly.
- [x] `callgraph_builder._try_merge_repo_signal_packs()` — hook that merges
  `repo_signal_callgraph.json`, `repo_signal_symbols.json`, and
  `repo_signal_summary.json` from `review_engine/context/` when present.
  Activates automatically when repo-signal starts writing intelligence packs to
  disk; no-op until then. Status surfaced in `build_repo_context` output.
- [x] `review_engine/context_selector.py` — `ContextSelector` enforces a 12 000-
  char budget (~3 000 tokens) on injected context. Priority order: past findings
  (2) before cross-file context (3). High-priority pieces are truncated rather
  than dropped when budget is tight. Wired into `review_file` after loading
  `past_context` and `cross_file_ctx`, before either review branch.

---

### Phase 3 — Semantic Review Memory (done)

Goal: intelligent long-term memory for the review engine.

- [x] `review_engine/review_memory.py` — local persistent review history;
  `ReviewMemory` saves/retrieves findings per file, formats past context
  for injection into future reviews (max 5 findings, capped 10 entries/file)
- [x] `review_file` wired to memory: loads past context before model call,
  saves structured findings after; past findings shown as `## Previous review context`
- [x] `list_review_history` MCP tool — summary of all reviewed files
- [x] `get_last_review` MCP tool — full last review for a specific file
- [x] `reviews/skills/markdown-review.md` + `reviews/skills/json-review.md` —
  review skills for `.md` and `.json` file types; wired into review_router
- [x] Cross-file reasoning: `_build_rich_cross_file_context()` injects arch role,
  top public symbols, and last review summary (finding count + severity
  distribution) for every file that imports or is imported by the file under
  review. Backed by `callgraph.json` (Phase 2) + `ContextSelector` (Phase 2).
  Files are no longer reviewed in isolation.
- [ ] Persist coding conventions extracted from reviews into architecture memory
  — deferred to v1.2.0 (Architecture memory), where it belongs structurally.

---

### Phase 4 — Multi-Pass Review Engine (done)

Goal: higher quality through structured pipeline.

- [x] `review_engine/multi_pass_reviewer.py` — `MultiPassReviewer` class:
  - Pass 1: structural analysis (responsibility, patterns, hotspots, ≤400 tokens)
  - Pass 2: contract-driven review enriched with structure context (≤2048 tokens)
  - Pass 3: consistency pass — doc vs runtime divergence (docstrings, names,
    type hints vs actual behavior; ≤1024 tokens)
  - Pass 4: deduplication — merges Pass 2 + Pass 3 findings, keeps highest
    severity per location, drops near-duplicate bodies (pure Python, no API call)
- [x] `review_file(deep=True)` — single-pass stays default; `deep=True` runs
  all 4 passes, returns formatted + deduplicated findings, ~3x API calls

---

### Phase 5 — Advanced Engineering Review (done)

- [x] `--risk` mode: `mode="security"` in `review_file` via `reviews/contracts/security-review.md`
  covers subprocess injection, path traversal, prompt injection, secret leakage,
  env forwarding, osascript injection
- [x] `review_engine/drift_detector.py` — `DriftDetector` checks: tool count vs
  README/TOOL_SAFETY.md/tool_contracts.json, contract coverage (all tools in JSON),
  phantom contracts (JSON tools not in server), safety doc coverage, arch map freshness
- [x] `detect_architecture_drift` MCP tool — exposes DriftDetector on the MCP surface

---

### Phase 6 — Autonomous Review Runtime (done)

- [x] `review_diff` MCP tool — continuous review triggered by git diff: reviews all
  `.py/.sh/.md/.json` files changed in the working tree or staging area, capped at 10
- [x] `review_repo` MCP tool — agentic review: prioritizes the least-recently-reviewed
  Python files in the repo (uses review memory to order by staleness), max 20 files
- [ ] Review TUI: severity history, semantic context display (deferred — out of scope for CLI)

---

## Runtime Consolidation

mq-mcp has reached a transition point. The system no longer lacks capability.

The functional capacity already exceeds many established AI runtime projects.
What was missing was a central model for how the system understands itself.

`docs/RUNTIME_CONTRACT.md` is the first output of this phase — the authoritative
identity contract. The remaining interventions make the runtime self-inspecting,
self-documenting, and structurally resistant to architectural drift.

Strategic principle: **no new features until the existing runtime is
self-describing, verifiable, and self-reflective**.

---

### v1.1.0 — Runtime self-inspection

Goal: the runtime can analyze its own architecture, verify its own contracts,
and surface drift between documentation and implementation.

- [x] `review_runtime_contract` MCP tool — reviews `docs/RUNTIME_CONTRACT.md`
  against actual server state: structural checks (path resolvers, no-auto-commit,
  _redacted_env) + AI architecture pass with injected tool count and safety class
  breakdown
- [x] Extend `detect_architecture_drift` — checks 8-10: RUNTIME_CONTRACT.md
  existence (RISK), freshness relative to server.py (NOTE/WARNING), and reference
  document existence for all docs listed in the contract's reference table
- [x] `list_architecture_docs` MCP tool — inventory of all docs in
  `docs/architecture/`, with last-modified timestamps and freshness status
  relative to `server.py` mtime
- [x] `review_architecture_doc` MCP tool — applies the `architecture` review
  contract to a named architecture document, injecting current runtime state
  (tool count, safety classes, actual server mtime) so the model can detect
  stale counts, incorrect classifications, and undocumented behaviors
- [x] Cross-file semantic similarity: `_build_rich_cross_file_context()` pulls
  architecture role, top public symbols, and last review summary for every file
  that imports or is imported by the file under review. Injected into both
  single-pass and deep-mode `review_file`. Removes the file-isolation barrier.
- [x] Golden reviews for `.md` and `.json` file types —
  `reviews/golden/system-overview-md-markdown-review.md` (5 findings:
  stale tool count, incomplete router table, stale pipeline diagram, missing
  file responsibilities, static date pattern) and
  `reviews/golden/tool-contracts-json-review.md` (5 findings: version drift,
  Swedish descriptions, free-text resolver field, empty examples, undeclared
  side_effects vocabulary).

---

### v1.2.0 — Architecture memory

Goal: durable, structured memory for design decisions and architectural intent —
not just review findings.

The current `review_engine/memory/review_history.json` stores what the review
engine found. Architecture memory stores why the system is designed as it is.

- [x] `architecture_memory/` directory — structured ADR-style entries:
  `decisions/` (ADR-001–005), `rejected/` (REJ-001), `boundaries/` (BND-001–002),
  `philosophy/` (PHI-001–002). 8 seed entries covering path resolvers, no-auto-commit,
  safety classes, review contracts, secret handling, cognition ownership,
  execution vs orchestration, determinism, and context quality.
- [x] `review_engine/architecture_memory.py` — `ArchitectureMemory` class: `list_all()`,
  `list_by_category()`, `get(id)`, `relevant_for(file_path)`, `format_context_block()`,
  `record()`. Relevance matching by area keyword against file path; philosophy entries
  match all files.
- [x] `list_architecture_decisions` MCP tool — lists all entries with ID, status,
  category, title (Class A, read-only)
- [x] `get_architecture_decision` MCP tool — returns full text by ID (Class A)
- [x] `record_architecture_decision` MCP tool — writes a new ADR to
  `architecture_memory/{category}/` (Class C, does not commit)
- [x] ADR injection in `review_file` — `format_context_block()` injects up to 3
  relevant ADRs (decision body, capped at 300 chars each) at priority 1 in
  `ContextSelector` — highest priority, before past findings and cross-file context.
  Deep mode prepends ADRs to `cross_file_ctx`.
- [x] `review_engine/convention_extractor.py` — `ConventionExtractor` runs a single
  model call to extract generalizable coding conventions from review findings.
  Output format: `CONVENTION / AREA / RATIONALE` blocks, parsed into structured entries.
  Deduplicates against existing convention titles before writing.
- [x] `extract_coding_conventions` MCP tool — loads last review from ReviewMemory,
  runs ConventionExtractor, saves each convention to `architecture_memory/decisions/`
  with `status: convention`. Conventions are immediately injected into future reviews
  of matching files via the existing ADR context mechanism (Class C).

---

### v1.3.0 — Orchestration boundary formalization

Goal: make the mq-agent / mq-mcp boundary explicit, machine-readable, and
verifiable — not just documented in prose.

- [x] `docs/ORCHESTRATION_CONTRACT.md` — formal contract defining:
  - what mq-agent is allowed to invoke
  - what return shapes it can rely on
  - what side effects it must never assume
  - how context flows from mq-agent into mq-mcp and back
- [x] Document cross-repo input/output contracts:
  - repo-signal exports repo intelligence packs
  - mq-image-analyze exports visual analysis JSON
  - mq-hal exports runtime and model health summaries
  - mq-agent routes review/orchestration requests to mq-mcp
- [x] `validate_orchestration_contract` MCP tool — verifies that the current
  tool set satisfies the orchestration contract: all caller-visible tools are
  documented, no undeclared side effects, no missing error prefixes
- [x] Profile validation: verify that each profile in `profiles/` restricts
  tool access to the minimum required for its declared use case
- [x] Semantic coupling audit: error prefix consistency checked; profile
  max-class violations found and corrected across 5 profiles

---

### v1.4.0 — Semantic memory layer

Goal: give the runtime a proper long-term knowledge store that is separate
from architecture decisions (ADRs) and review history. Blueprint §8.

The distinction matters:

```text
architecture_memory/  — decisions, boundaries, philosophy (structural)
review_engine/memory/ — per-file review history (operational)
semantic_memory/      — long-term reusable knowledge (semantic)
```

**What semantic memory stores:**
- Summaries of README, ROADMAP, and key architecture docs
- Contracts and review examples (indexed, not raw text)
- Extracted conventions (already done via extract_coding_conventions)
- Tool docs and safety notes
- Cross-repo facts (e.g. "repo-signal outputs callgraph.json to disk")

**What it does NOT store:**
- Entire raw repos
- Generated build artifacts
- Large binaries or noisy logs

Items:

- [ ] `semantic_memory/` directory + `SemanticMemory` class with
  `store(key, content, tags)`, `search(query, max=5)`, `get(key)`, `list()`
- [ ] `store_semantic_memory` MCP tool — writes a named knowledge item with
  tags for retrieval (Class C, writes to `semantic_memory/`)
- [ ] `search_semantic_memory` MCP tool — keyword/tag search over stored items,
  returns ranked matches (Class A)
- [ ] `get_semantic_memory` MCP tool — retrieves a specific item by key (Class A)
- [ ] Bootstrap ingestion: index README, ROADMAP, RUNTIME_CONTRACT.md,
  ORCHESTRATION_CONTRACT.md, TOOL_SAFETY.md into semantic_memory at startup
  (lazy, on first search)
- [ ] Integration with `review_file` context: semantic memory injected at
  priority 0 (above ADRs) when a match is found for the file being reviewed
- [ ] `list_semantic_memory` MCP tool — inventory of stored items (Class A)
- [ ] Docs: update ORCHESTRATION_CONTRACT.md §3 declared side effects table

---

### v1.5.0 — Risk analysis layer

Goal: go beyond doc review — give the runtime explicit risk and security
reasoning modes. Blueprint §10.

The review engine already has severity levels (RISK, ARCHITECTURE, WARNING).
This phase adds structured risk *modes* so callers can request targeted
security or architecture analysis without running a full review.

**Risk modes:**

```text
security  — subprocess safety, shell injection, env leakage, unsafe fs access
            secret exposure, path traversal, MCP exposure surface
risk      — class D tools invoked without approval gates, missing contracts,
            undeclared side effects, stale safety docs
architecture — boundary violations, coupling, responsibility drift,
               cross-repo contract gaps
```

Items:

- [ ] `risk_review_file` MCP tool — targeted risk pass on a single file with
  declared mode (`security`, `risk`, `architecture`). Returns findings using
  the fixed severity vocabulary (CRITICAL/RISK/WARNING). Class A.
- [ ] `risk_review_diff` MCP tool — risk pass over current git diff. Same
  modes. Class A.
- [ ] Risk contract in `reviews/contracts/risk-review.md` — defines what the
  security/risk/architecture passes look for and how to format findings
- [ ] Security skill in `reviews/skills/security-review.md` — file-type-aware
  security patterns (Python subprocess, shell, env, path)
- [ ] Severity engine update: add `CRITICAL` level above `RISK` for findings
  that represent immediate exploitable vulnerabilities
- [ ] `detect_security_patterns` helper — grep-based pre-scan for known
  dangerous patterns (`os.system`, `eval`, `exec`, `shell=True`, hardcoded
  secrets) before API call; injects findings as context
- [ ] Integration: `review_file(mode="risk")` routes through the risk contract
  rather than the standard comment contract

---

### v1.6.0 — Generated artifacts + repo-signal merge

Goal: close the loop between repo-signal's intelligence output and mq-mcp's
context builder. Blueprint §6.1, §3.3.

repo-signal already has a merge hook in `callgraph_builder._try_merge_repo_signal_packs()`.
This phase activates it fully by defining the on-disk format and adding the
generated artifacts directory structure.

**Expected repo-signal output files (when repo-signal writes them):**

```text
review_engine/context/repo_signal_callgraph.json  — merged into callgraph.json
review_engine/context/repo_signal_symbols.json    — merged into symbol index
review_engine/context/repo_signal_summary.json    — repo-level health summary
```

**Generated artifacts directory:**

```text
generated/
├── symbols/          — symbol_index.json, per-file symbol exports
├── callgraphs/       — callgraph snapshots with timestamps
└── architecture/     — architecture_map.json, ownership_map.json
```

Items:

- [ ] `generated/` directory with `.gitkeep` and `generated/.gitignore`
  (exclude snapshots from version control)
- [ ] `build_repo_context` extended: write `architecture_map.json` to
  `generated/architecture/` in addition to `callgraph.json`
- [ ] `architecture_map.json` schema: maps file path → role label, public
  symbols, last review timestamp, hub score
- [ ] `ownership_map.json` schema: maps file path → author (from git blame),
  change frequency, last modified
- [ ] `export_symbol_index` MCP tool — writes current callgraph symbols to
  `generated/symbols/symbol_index.json` in a format repo-signal can consume
  (Class C)
- [ ] Activate `_try_merge_repo_signal_packs()`: once repo-signal publishes
  its packs, the merge hook auto-activates; document the expected file paths
  and schema in `docs/ORCHESTRATION_CONTRACT.md §5`
- [ ] `repo_signal_status` MCP tool — reports whether repo-signal packs are
  present, their age, and whether they have been merged into the callgraph
  (Class A)

---

## Long-term ideas

These are intentionally not scheduled yet.

**Model routing strategy** — three tiers matched to task depth:

| Mode | Model | Use case |
| --- | --- | --- |
| Fast | Local small (qwen3:4b, llama3) | Single-file comment review, quick checks |
| Deep | Local large (qwen3:14b, deepseek-coder) | Multi-pass review, architecture analysis |
| Architecture | Cloud (GPT-4, Claude Opus) | Cross-repo reasoning, design decisions |

The fast tier enables offline-first review with no API cost. The routing
decision should be made automatically based on file size, review mode, and
available local models.

**Review TUI** — terminal-native review surface showing severity history,
cross-file graph, semantic context panel, and architecture role for the
current file. Leverages `callgraph.json` and `architecture_map.json` as
data sources.

Other ideas:

- Bridget voice mode
- Bridget terminal avatar mode
- local event history
- repo health history
- MCP tool marketplace
- integration with mq-ums
- cross-repo tool inventory
- visual safety map — runtime dependency graph, orchestration topology
- generated architecture diagrams from architecture_memory
- drift visualization: doc vs implementation divergence over time
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
Runtime Consolidation — v1.1.0 Runtime self-inspection
```

The system's functional capacity is sufficient. The leverage point is now
making the runtime self-describing and self-verifying.

Immediate priorities:

1. `review_runtime_contract` MCP tool — runtime reviews its own contract
2. Extend `detect_architecture_drift` with RUNTIME_CONTRACT.md coverage check
3. Cross-file semantic similarity — carry-over from Phase 3
4. Golden reviews for `.md` and `.json` file types

Keep validating releases with `./scripts/release-check.sh` and only add new
tool surface when safety metadata, tests, profiles, and docs move with it.
