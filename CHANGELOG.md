# Changelog

## Unreleased

### Added

* Bridget interactive session foundation (v2.1.0, `mq-mcp/bridge.py`):
  * `bridget --chat` — an explicit interactive REPL. One MCP `ClientSession`
    and one system message stay alive for the whole session; tools are
    discovered once at start. Per turn: read a line → `run_turn` → print →
    keep context. Exits on `exit`/`quit`/`q`/Ctrl-D/Ctrl-C. Input is read from
    stdin and prompts/answers go to `/dev/tty` (falling back to stdout), so
    piped input works and output survives a captured stdout. Not the default —
    one-shot stays the default for scripts, aliases, and automation.
  * Multi-round tool loop (bugfix): `run_turn` now runs a bounded loop
    (`MAX_TOOL_ROUNDS = 10`) that passes `tools=` on every model call, so DO
    MODE can chain several sequential tool calls instead of one round plus a
    final answer. `--do` forces a tool only on the first round; per-command
    approval and the `--do`-gated `shell_exec` are unchanged.
  * REPL context-window management: rough token estimate, per-model budget
    (`BRIDGET_CONTEXT_BUDGET`), whole-turn-block trimming that never drops the
    system message and preserves tool_call/tool pairing, plus
    `MAX_MESSAGES` / `MAX_TOOL_OUTPUT_CHARS` truncation of oversized tool output.
  * REPL persistence: a `--chat` session is recorded once at exit (not per
    turn) as a single memory entry — last prompt/answer plus turn count,
    duration, tools across all turns, `do_mode`, `chat_mode` — so short
    sessions do not push older one-shot sessions out of the five-session
    rolling window. `bridget --history` tags REPL sessions with their turn
    count; `bridget --continue` surfaces the previous REPL session summary.
    One-shot history keeps its existing stored shape.
* `learn_inbox_draft` (Class A, read-only): standardizes the inbox-candidate →
  `record_learning` mapping. Selects exactly one pending candidate (commit SHA
  prefix and/or `pattern_name`) and returns a review-ready draft
  (`task`/`lesson`/`validation`/`risk`/`repo`/`source`/`tags`). Preview-first —
  it writes neither the curated lessons store nor the inbox queue, and
  `validation` is always emitted as a `MANUAL VALIDATION REQUIRED` instruction,
  never an auto-filled truth claim, so promotion stays a human decision. Backed
  by pure mappers in `learn_engine.py` (`build_record_learning_draft`,
  `draft_inbox_candidate`) and `tests/test_learn_inbox_draft.py`.

## 2.0.0 - 2026-06-15

Release Gate v2 + deterministic readiness.

### Added

* Release Gate v2: four new deterministic checks completing the v2.0.0 scope —
  `lint_type_quality` (optional `--lint-command`, warns when not run),
  `contract_drift` (blocks when `@mcp.tool()` count diverges from
  `docs/tool_contracts.json`), `unsafe_commands` (blocks ungated shell/eval/exec
  in server/bridge entrypoints; ignores string-literal pattern definitions and
  honors `# nosec`), and `perception_review` (read-only surfacing of
  mq-image-analyze risk signals). `release_gate_run` and `release-gate run` gain
  a `lint_command` / `--lint-command` argument.
* Skills: `learn-engine-maintainer` and `brain-maintainer` now own the learning
  engine and Obsidian second-brain surfaces.
* `scripts/check-skills.sh`: validates skill frontmatter, cross-references,
  referenced paths, and SKILLS.md sync; wired into the docs-consistency
  workflow. `--fix` regenerates SKILLS.md from frontmatter.

### Changed

* All skills now include an `## Evals` section (should/should-not-trigger).
* `integration-stack-maintainer` points to `generated/tool-index.json` instead
  of a hardcoded integration tool list.
* `docs-maintainer` no longer routes to the non-existent `repo-product-auditor`
  skill.
* CHANGELOG 1.11.0 entry corrected: brain tools are `brain_status` and
  `brain_record_decision/review/session/learning` + `brain_promote_learning`
  (not `insight/pattern/question`), image tools are `image_analyze`,
  `image_analyze_ui`, `image_observe_architecture` (not `image_ocr`/`image_diff`).

### Fixed

* `scramble_print` in `bridge.py` and `ask.py` now animates only on an
  interactive TTY. Piped or captured output (validate.sh, CI, logs) previously
  received the raw scramble bytes — three random characters plus backspace per
  visible character — which rendered as garbled text wherever backspaces are
  not interpreted.

## 1.11.0 - 2026-06-10

### Added

* Brain/Obsidian tools: `obsidian_writer` module with `brain_status` (Class A) and
  `brain_record_decision`, `brain_record_review`, `brain_record_session`,
  `brain_record_learning`, `brain_promote_learning` (Class C) — routes mq-mcp
  findings directly into the Obsidian second brain.
* Zephyr-workbench integration: 4 Class B MCP tools exposed via `zephyr_*` routes.
* mq-image-analyze integration: 3 Class B MCP tools (`image_analyze`,
  `image_analyze_ui`, `image_observe_architecture`) exposed as first-class mq-mcp tools.
* UMS tooling: `ums_command_catalog` (Class A) and `ums_audit_log` (Class A).
* repo-signal JSON tools: `repo_signal_report`, `repo_signal_suggest`,
  `repo_signal_positioning` — structured readiness output without shell parsing.
* Ollama provider scaffold: provider module, schemas, docs, and fixtures for optional
  local learn extraction (`models/ollama/Modelfile.mq-learn`, `docs/LEARN_OLLAMA.md`).
* mq-agent learn compatibility aliases: `learn_status`, `search_learned_patterns`,
  `explain_learned_pattern`.
* `learn_hygiene` tool and Release Gate v2 `learn_hygiene_pass` check — flags duplicate,
  invalid, low-confidence, and unvalidated learn records before release.
* `learn_extract_from_last_review` (dry-run) — extracts learn items from the most
  recent review without persisting.
* Release gate additions: learn hygiene gate, repo-signal readiness gate, perception
  artifact gate.
* `docs/LEARN_CONTRACT.md` — learn contract policy and optional Ollama extraction scope.

### Fixed

* Auto-load `.env` on server startup via `python-dotenv` — no manual export required.
* `record_learning` KeyError on result dict when key is missing.
* Unwrap single-key wrapper dict in `extract_learn_items`.
* Four static analysis errors in `server.py`.
* Registered 6 brain tools in safety docs and tool contracts.

## 1.10.0 - 2026-05-31

* Completed Runtime Truth + Safety Governance roadmap (Phases 1–9):
  * Phase 1: synced all version signals (VERSION, README badge, stability.json,
    tool_contracts.json), added GitHub releases v1.6.0–v1.9.0.
  * Phase 2: `scripts/check-runtime-truth.sh` — 9 deterministic checks wired
    into `scripts/validate.sh`.
  * Phase 3: `mq-mcp/tool_registry.py` with 11 tool categories; `mq-mcp tools
    --json/--safety/--markdown/--export`.
  * Phase 4: safety class enforcement in `check-tool-contracts.sh`; 30 new
    tests in `test_tool_contracts.py` and `test_safety_classes.py`.
  * Phase 5: five review contracts — `runtime-truth`, `safety-contract`,
    `release-readiness`, `memory-hygiene`, `orchestration-boundary`.
  * Phase 6: `semantic_memory/POLICY.md`, `schema.json`,
    `check-semantic-memory.sh`; `mq-mcp memory audit/count/list`.
  * Phase 7: `docs/orchestration-boundary.md`; Ecosystem section in README.
  * Phase 8: `scripts/release-check.sh` rewritten with 12 sections, CI check,
    `--dry-run`; `release.sh` calls gate as first step.
  * Phase 9: `export_release_state()`, `export_profile_index()`,
    `check-generated-artifacts.sh` (5 deterministic artifacts).
* Added `learning_status` MCP tool (Class A): learn layer stats by source,
  risk, and repo.
* Added `learn_from_review` MCP tool (Class C): creates a learning record from
  the last review findings for a file.
* Added `learn_from_diff` MCP tool (Class C): creates a learning record with
  current git diff as context.
* Added `bootstrap_learning_memory` MCP tool (Class C): seeds the learn layer
  from architecture memory ADRs; idempotent.
* Tool count: 91 → 95.

## 1.9.0 - 2026-05-29

* Fixed `_detect_security_patterns` false positives: Python string literals
  are now blanked via `tokenize` before pattern matching, preventing matches
  in description strings that mention the patterns they document. Only strings
  containing spaces are blanked; short values (API keys, tokens) are preserved.
  Shell files are scanned as-is. New `_blank_python_strings()` helper added.
* Added `list_review_skills` MCP tool (Class A): lists path-prefix routes,
  extension routes, and the security-mode override, with availability status
  for each skill file.
* Added `ADR-006`: documents risk analysis tools using pre-scan before API
  calls, CRITICAL severity reserved for risk/security modes, and string-literal
  stripping rationale.
* Added `§8 WARN acceptance policy` to `docs/ORCHESTRATION_CONTRACT.md`:
  table defining when each WARN is acceptable vs. requires action.
* Added check 7 to `validate_orchestration_contract`: Class C tools not in
  any profile and not in `_INTENTIONALLY_PROFILE_FREE` emit WARN. All current
  Class C tools are intentionally profile-free (require explicit user approval).
* Fixed `import re` missing at module level in server.py (required by the
  `_STRIP_STRINGS_RE` constant).
* Documented subprocess side effects in `build_ownership_map()` docstring
  and updated `ORCHESTRATION_CONTRACT.md §3` side effects table for
  `build_repo_context`.
* Tool count: 75 → 76.

## 1.8.0 - 2026-05-29

* Completed remaining v1.6.0 items — `generated/architecture/` artifacts:
* Added `review_engine/generated_artifacts.py` with two builders:
  * `build_rich_architecture_map()` — writes `generated/architecture/architecture_map.json`
    (schema `architecture_map.v1`): per-file role, public_symbols, last_review_timestamp,
    hub_score (from callgraph importers).
  * `build_ownership_map()` — writes `generated/architecture/ownership_map.json`
    (schema `ownership_map.v1`): per-file author (most frequent committer),
    change_frequency (commit count), last_modified (ISO timestamp).
    Scans last 200 commits via one `git log` call.
* Extended `build_repo_context` (Class C) to call both builders after the
  callgraph build. Output now reports both generated files with schemas.
* Updated `docs/RUNTIME_CONTRACT.md` — added Generated artifacts section
  under Context model.
* All v1.6.0 ROADMAP items now marked `[x]`.

## 1.7.0 - 2026-05-28

* Added `CRITICAL` severity level to `review_engine/severity_engine.py` —
  placed above `RISK` in `SEVERITY_ORDER`; `has_blocking_findings` updated to
  include CRITICAL.
* Added `reviews/contracts/risk-review.md` — defines the `risk` review mode:
  covers approval gate gaps, undeclared side effects, contract staleness, and
  cross-repo boundary drift. Severity labels: CRITICAL, RISK, WARNING, NOTE.
* Added `reviews/skills/security-review.md` — file-type-aware security pattern
  guide injected into security and risk mode prompts. Covers Python, shell,
  JSON, and MCP tool definition patterns.
* Added `_detect_security_patterns()` internal helper — grep-based pre-scan
  for 11 Python and 3 shell dangerous patterns (os.system, eval, exec,
  shell=True, pickle, hardcoded secrets, curl|bash, etc.). Returns
  `[SEVERITY] file:line\ndescription` blocks, no API call.
* Added `route_file_for_mode()` to `review_engine/review_router.py` —
  overrides skill selection to inject `security-review.md` for security and
  risk modes, regardless of file type.
* Added `risk_review_file` MCP tool (Class A) — targeted risk pass with
  declared mode (`security`, `risk`, `architecture`). Runs pre-scan, injects
  results into model context, calls API under the matching contract, saves to
  review memory.
* Added `risk_review_diff` MCP tool (Class A) — risk pass over all changed
  files in working tree or staging area, delegates per file to `risk_review_file`.
* Updated `scripts/generate_tool_contracts.py`: added metadata for
  `risk_review_file` and `risk_review_diff`.
* Regenerated `docs/tool_contracts.json` — 75 tools.
* Tool count: 73 → 75.

## 1.6.0 - 2026-05-28

* Activated `_try_merge_repo_signal_packs()` in `review_engine/callgraph_builder.py`:
  reads from `.repo-signal/exports/` (repo-signal v1.1.0 location), handles
  `callgraph.v1` (`source/target` → `from/to` conversion), `symbol_index.v1`
  (flat list → per-file group map), `repo_summary.v1`, and `risk_map.v1` (new).
  Hub files refreshed from merged importers. No-op when exports directory absent.
* Added `generated/` directory structure: `symbols/`, `callgraphs/`,
  `architecture/` with `.gitkeep` files; `generated/.gitignore` excludes JSON
  snapshots from version control.
* Added `export_symbol_index` MCP tool (Class C) — writes in-memory callgraph
  symbol map to `generated/symbols/symbol_index.json`; requires
  `build_repo_context` to have run first.
* Added `repo_signal_status` MCP tool (Class A) — reports presence, schema,
  and age of each `.repo-signal/exports/` pack; reports last merge status from
  `review_engine/context/callgraph.json`.
* Updated `scripts/generate_tool_contracts.py`: added metadata for all 23
  tools added since v1.0.0 (review engine, architecture memory, semantic
  memory, orchestration contract, and new v1.6.0 tools).
* Regenerated `docs/tool_contracts.json` — now covers all 73 tools.
* Tool count: 71 → 73.

## 1.4.0 - 2026-05-28

* Added `semantic_memory/` module with `SemanticMemory` class:
  `store(key, content, tags)`, `get(key)`, `search(query, max)`,
  `search_for_file(file_path, max)`, `list_all()`, `format_context_block()`,
  `delete(key)`. Storage: `semantic_memory/store.json`.
* Added 5 MCP tools (Class A/C) for semantic memory:
  * `store_semantic_memory` — Class C, writes to store.json
  * `search_semantic_memory` — Class A, keyword search with ranked results
  * `get_semantic_memory` — Class A, exact-key retrieval
  * `list_semantic_memory` — Class A, full index with previews
  * `bootstrap_semantic_memory` — Class C, ingests README, ROADMAP,
    RUNTIME_CONTRACT.md, ORCHESTRATION_CONTRACT.md, TOOL_SAFETY.md;
    idempotent (skips unchanged docs)
* Integrated semantic memory into `review_file` context assembly at priority 0
  (above ADRs at priority 1) via `SemanticMemory.format_context_block()`.
  Injected as `semantic_section` in single-pass mode user prompt.
* Updated `docs/ORCHESTRATION_CONTRACT.md` §3 side-effects table:
  `store_semantic_memory` and `bootstrap_semantic_memory` declared.
* Tool count: 66 → 71.

## 1.3.0 - 2026-05-28

* Added `docs/ORCHESTRATION_CONTRACT.md` — formal caller boundary contract with
  7 sections: invocation contract (approval gate model), return contract
  (severity vocabulary, output structure), side effect contract (declared
  persistent side effects table), context flow diagram (priority order:
  ADRs > past_context > cross_file_ctx), cross-repo contracts (mq-agent,
  repo-signal, mq-hal, mq-image-analyze), profile access model, and 7
  always-true guarantees.
* Added `validate_orchestration_contract` MCP tool — 12 deterministic checks:
  contract freshness, profile recommended_tools registration, per-profile max
  safety class enforcement, write:true → Class C, Class D → subprocess:true,
  error return prefix consistency. Returns [PASS]/[FAIL]/[WARN] lines. Class A.
* Fixed profile violations found by the new tool: removed `hal_repo_report`
  (Class D) from `claude-desktop`, `mq-agent`, `openai-bridge`; removed
  `validate_project` (Class D) from `codex`, `repo-only`; removed
  `update_repo_file` from `repo-only` (Class C, now matches contract A/C).
* Updated `docs/ORCHESTRATION_CONTRACT.md` profile max-class table: `repo-only`
  A/C (needs update_repo_file), `claude-desktop` A/B (needs repo-signal).
* Standardised error return prefixes: `review_file deep mode failed` →
  `review_file failed (deep mode)`, `review_file API call failed` →
  `review_file failed (API call)`, `review_diff: git diff failed` →
  `review_diff failed (git diff)`.
* Tool count: 65 → 66.

## 1.2.0 - 2026-05-28

* Added `architecture_memory/` directory with 8 seed entries across four
  categories: `decisions/` (ADR-001–005), `rejected/` (REJ-001),
  `boundaries/` (BND-001–002), `philosophy/` (PHI-001–002). Covers path
  resolvers, no-auto-commit, safety classes, review contracts, secret handling,
  cognition ownership, execution vs orchestration, determinism, and context
  quality.
* Added `review_engine/architecture_memory.py` — `ArchitectureMemory` class
  with `list_all()`, `get()`, `relevant_for()`, `format_context_block()`, and
  `record()`. Area keyword matching injects relevant ADRs into reviews;
  philosophy entries match all files.
* Added `list_architecture_decisions` MCP tool — lists all architecture memory
  entries with ID, status, category, and title (Class A).
* Added `get_architecture_decision` MCP tool — returns full entry text by ID
  (Class A).
* Added `record_architecture_decision` MCP tool — writes a new ADR to
  `architecture_memory/` with YAML frontmatter (Class C, does not commit).
* Added `review_engine/convention_extractor.py` — `ConventionExtractor` runs a
  single model call to extract generalizable coding conventions from review
  findings. Deduplicates against existing convention titles.
* Added `extract_coding_conventions` MCP tool — loads last review from
  ReviewMemory, extracts conventions, saves each to `architecture_memory/decisions/`
  with `status: convention`. Conventions inject into future reviews via the
  ADR context mechanism at priority 1 (Class C).
* ADR injection in `review_file` — up to 3 relevant architecture decisions
  injected at highest priority in `ContextSelector`, before past findings and
  cross-file context.
* Tool count: 64 → 65.

## 1.1.0 - 2026-05-27

* Added `review_runtime_contract` MCP tool — structural + AI pass that verifies
  `docs/RUNTIME_CONTRACT.md` claims against actual server state (path resolvers,
  no-auto-commit, `_redacted_env`, tool count, safety class breakdown).
* Extended `detect_architecture_drift` with checks 8–10: RUNTIME_CONTRACT.md
  existence (RISK), freshness relative to server.py (NOTE/WARNING), and reference
  document existence for all docs listed in the contract.
* Added `list_architecture_docs` MCP tool — inventory of `docs/architecture/`
  with freshness status relative to server.py mtime.
* Added `review_architecture_doc` MCP tool — applies the architecture review
  contract to a named doc with injected runtime state.
* Added `review_engine/callgraph_builder.py` — Python AST cross-file import
  graph. Outputs `review_engine/context/callgraph.json` (imports, importers,
  hub_files, symbols, edges). Wired into `build_repo_context` and `review_file`.
* Added `_build_rich_cross_file_context()` — replaces bare file names with
  architecture role, top public symbols, and last review summary for every related
  file. Files are no longer reviewed in isolation.
* Added `review_engine/context_selector.py` — `ContextSelector` enforces a
  12 000-char budget on injected context. Past findings (priority 2) are preferred
  over cross-file context (priority 3) when budget is tight.
* Added `review_engine/callgraph_builder._try_merge_repo_signal_packs()` — hook
  that merges repo-signal intelligence packs when available. No-op until
  repo-signal writes packs to disk.
* Added golden reviews for `.md` (SYSTEM_OVERVIEW.md) and `.json`
  (tool_contracts.json) file types under `reviews/golden/`.
* Updated `docs/RUNTIME_CONTRACT.md` — authoritative identity and execution
  contract for the runtime.
* Completed Review Engine Phases 2, 3 (remaining items), and 4.

## 1.0.0 - 2026-05-26

* Added `docs/stability.json` and `docs/stability.md` as the v1 stable
  local MCP platform baseline.
* Added `scripts/check-stability.py` and wired it into `scripts/validate.sh`,
  `scripts/release-check.sh`, and GitHub Actions.
* Added `mq-mcp stability show` and `mq-mcp stability validate`.
* Documented stable startup, metadata, profiles, safety boundaries, validation,
  install flow, troubleshooting, example workflows, GitHub Pages, and release
  evidence.
* Updated version surfaces to `1.0.0`.

## 0.8.0 - 2026-05-26

* Added versioned MCP profile templates under `profiles/` for Claude Desktop,
  Codex, mq-agent, OpenAI bridge, local macOS, repo-only, read-only, and
  developer workflows.
* Added `mq-mcp profiles list`, `profiles show`, `profiles path`, and
  `profiles validate`.
* Added `scripts/check-profiles.py` and wired it into `scripts/validate.sh`.
* Reworked `docs/profiles.md` around choosing the smallest safe profile.
* Updated client and install docs to point at validated profile templates.
* Added tests for profile template contracts and CLI profile discovery.

## 0.7.0 - 2026-05-26

* Added observability endpoints: `/health`, `/tool-count`, `/server-info`,
  and `/diagnostics`.
* Added optional request logging via `MQ_MCP_REQUEST_LOG=1` with no secret
  values in logs.
* Added `mq-mcp health`, `mq-mcp info`, `mq-mcp report`, and
  `mq-mcp bundle` commands.
* Added redacted diagnostics output for local environment and repository
  state.
* Added optional validation capture in `mq-mcp report --validate` and
  `mq-mcp bundle --validate`.
* Added tests for observability JSON and secret redaction.

## 0.6.0 - 2026-05-26

* Added packaged local `mq-mcp` CLI with `doctor`, `serve`, `validate`,
  `tools`, `config path`, and `version` commands.
* Added `scripts/install.sh`, `scripts/upgrade.sh`, and
  `scripts/uninstall.sh` for repeatable local macOS setup and cleanup.
* Added optional zsh completion at `completions/_mq-mcp`.
* Added CLI tests for version, doctor JSON, and config path behavior.
* Updated install, upgrade, README, and GitHub Pages docs for the v0.6.0
  local install flow.
* Documented mqlaunch integration flow as part of the hardened local stack.

## 0.4.0 - 2026-05-26

* Added `scripts/generate_tool_contracts.py` — generates
  `docs/tool_contracts.json` from server.py introspection and a static
  metadata mapping (class, resolver, write, subprocess, side_effects).
* Added `docs/tool_contracts.json` — machine-readable tool contract file
  (schema_version: tool-contracts.v1) covering all 50 tools. Consumable
  by mq-agent and other clients without importing server.py.
* Added `scripts/check-tool-contracts.sh` — CI check that verifies every
  `@mcp.tool` in server.py has a matching entry in tool_contracts.json.
  Fails if any tool is missing or if the JSON is stale.
* Wired `check-tool-contracts.sh` into `scripts/validate.sh`.
* Added two steps to `.github/workflows/validate.yml`: tool contract check
  and a drift check (regenerates JSON and asserts git diff is clean).
* Updated ROADMAP: v0.4.0 scope done, all definition-of-done items checked.

## 0.3.1 - 2026-05-26

* Fixed stale tool count in README Proof section and Demo section:
  "19 tools" updated to "50 tools".
* Fixed stale tool count in `docs/index.html` meta description:
  "13 sandboxed tools" updated to "50 sandboxed tools".
* Refactored Bridget image selection: `choose_bridget_image()` with
  `_last_bridget_image` tracking — avoids repeating the same image
  twice in a row when multiple images are available.
* Simplified `BRIDGET_ASSET_GLOB` from multi-pattern list to single
  `"bridget*.jpg"` — non-Bridget and jpeg files excluded.
* Added five new Bridget local lines.
* Fixed `scripts/generate_screenshots.py` to discover Bridget images
  via glob instead of hardcoded filenames.
* Added tests: `test_find_bridget_images_uses_bridget_jpg_glob`,
  `test_choose_bridget_image_does_not_repeat_when_possible`.
* GitHub Actions green on `main`. All 36 tests pass.
  `validate.sh` and `release-check.sh` pass locally.

## 0.3.0 - 2026-05-25

* Added stable launcher command and documented MCP server profiles.
* Added setup examples for common MCP clients
  (Claude Desktop, Codex, mq-agent).
* Added complete troubleshooting page at `docs/troubleshooting.md`.
* Added example workflows and upgrade instructions at
  `docs/upgrade.md`.
* Made tool documentation easier to follow across
  `docs/TOOL_SAFETY.md` and `docs/TOOL_INVENTORY.md`.
* Made validation flow repeatable via `scripts/validate.sh` and
  `scripts/release-check.sh`.

## 0.2.3 - 2026-05-24

* Bridget face lines now dynamically generated via `mq-image-analyze`
  when available.
* Parallelized mq-image analysis with chafa rendering — lower latency
  on Bridget face trigger.
* Fixed Bridget face output routing to `/dev/tty` so it survives
  piped contexts.
* Added Claude Code subagents: `mq-project-context`,
  `mcp-tool-safety-reviewer`, `mcp-release-validator`.

## 0.2.2 - 2026-05-23

* Synced tool count to 19 across README, demo.md, and TOOL_SAFETY.md
  (README said "18", demo.md showed a stale 14-tool list).
* Fixed Python version requirement in docs/install.md from
  "3.14 or later" to ">=3.11".
* Updated demo.md tool list to include all 19 current MCP tools.
* Added Proof section to README.
* Added `scripts/release-check.sh` — pre-release gate covering shell
  syntax, Python compile, validate.sh, tests, version sync, and
  stale tool count detection.
* Added `.github/workflows/docs-consistency.yml` — CI checks for
  version sync, stale tool counts, and Python version accuracy in
  docs.
* Added bridge tool discovery smoke check for Bridget/MCP tool
  visibility.
* Added integration smoke check for mq-hal and repo-signal MCP tool
  wiring.
* Removed Bridget text face asset; Bridget face output now uses image
  assets only when available.

## 0.2.1 - 2026-05-18

* Added Bridget face identity asset.
* Added face trigger to `bridge.py` — prompts like "hur ser du ut",
  "visa dig", "who are you" show the face locally with zero API cost.
* Added Bridget face smoke-check to `scripts/validate.sh`.
* Synced `pyproject.toml` version to `0.2.1` and fixed description
  from placeholder.
* Added `resolve_allowed_local_file()` to `server.py` —
  `analyze_guitar_pro`, `open_in_app`, and `edit_image` now accept
  repo-relative or absolute paths, gated by `MQ_MCP_ALLOWED_PATHS`.
* Remaining 10 tools continue to use `resolve_repo_file()` —
  fully repo-scoped.
* Documented `MQ_MCP_ALLOWED_PATHS` in `mq-mcp/.env.example` and
  `docs/security.md`.
* Updated `docs/index.html` GitHub Pages landing page.
* Updated ROADMAP to mark v0.2.1 done.

## 0.2.0 - 2026-05-13

* Added documented MCP safety policy in `docs/security.md`.
* Added safety tests for repo-scoped file access and blocked paths.
* Added CI validation for shell syntax, Python compilation, project
  validation, and tests.
* Restricted `analyze_csv` to repository-root-safe paths.
* Clarified MCP tool scope in documentation.
* Cleaned up install guide references and replaced PDF install guide
  with Markdown documentation.
* Improved README with security policy and validation guidance.

## 0.1.3 - 2026-05-13

* Added GitHub Actions validation workflow.
* Added MCP server safety tests covering path escapes, blocklists, and edge cases.
* Added Markdown installation guide at `docs/install.md`.
* Replaced PDF installation guide with Markdown documentation.
* Made OpenAI client lazy so `bridge.py --tools` works without `OPENAI_API_KEY`.
* Updated README test and install guide references.

## 0.1.2 - 2026-05-13

* Added local validation flow via `scripts/validate.sh`.
* Added documented MCP tool inventory in README.
* Added bridge-driven project validation path.
* Added repo-aware MCP tools and safe file update support.
* Improved README with validation instructions.
* Updated roadmap to reflect completed documentation and validation work.

## 0.1.0 - 2026-05-12

* Initial repository setup.
* Added README baseline.
* Added MCP installation guide.
* Added docs folder and GitHub Pages landing page.
* Added issue templates and public readiness structure.
