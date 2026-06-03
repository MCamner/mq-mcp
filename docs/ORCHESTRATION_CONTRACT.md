# mq-mcp Orchestration Contract

This document defines the formal boundary between mq-mcp and its callers —
primarily mq-agent, but also Claude Desktop, the OpenAI bridge, Codex, and
any other MCP client.

The boundary is not aspirational. It is enforced structurally:

- Path resolvers reject access outside declared roots (ADR-001)
- No tool commits or pushes git state (ADR-002)
- Every tool has a declared safety class (ADR-003)
- Every tool output has a predictable structure (PHI-001)

Authoritative identity contract: `docs/RUNTIME_CONTRACT.md`
Architecture memory: `architecture_memory/`
Last updated: 2026-05-31 (v1.9.0).

---

## 1. Invocation contract

### What callers may do

- Invoke any tool by name with the declared argument types.
- Rely on tool output being a `str` (plain text or structured text).
- Pass file paths as repo-relative strings (not absolute paths).
- Set environment variables listed in `docs/architecture/SYSTEM_OVERVIEW.md`
  to configure runtime behavior.

### What callers must not do

- Pass absolute filesystem paths directly — resolvers will reject them unless
  they fall within `MQ_MCP_ALLOWED_PATHS`.
- Invoke Class C or D tools without explicit user confirmation in the calling
  orchestrator.
- Assume that a Class A tool has no side effects on external systems —
  review tools make OpenAI API calls which are billable and rate-limited.
- Chain tool calls that together produce a git commit or push — each tool is
  independently scoped; the chain does not inherit a broader permission.

### Approval gate model

| Tool class | Caller action required                                    |
| ---------- | --------------------------------------------------------- |
| A          | None — safe to auto-invoke                                |
| B          | None — safe to auto-invoke (may make network calls)       |
| C          | Explicit user approval — writes files                     |
| D          | Explicit user approval — opens apps or runs subprocesses  |

---

## 2. Return contract

### Output structure

All tools return a `str`. Callers must not assume JSON unless the tool
explicitly documents `--json` or `json=True` output.

Error returns always begin with `{tool_name} failed:` or `ERROR:`.
A caller that receives output starting with these prefixes must treat the
call as failed and not parse the remainder as success output.

Structured output that can be machine-parsed:

- `detect_architecture_drift` — `[SEVERITY] location\nbody` blocks
- `review_file` / `review_diff` / `review_repo` — `[SEVERITY] file:line\nbody` blocks
- `validate_orchestration_contract` — `[PASS]` / `[FAIL]` / `[WARN]` lines

### Severity labels

Review tools use a fixed severity vocabulary. Callers that parse review output
must handle exactly these labels (case-sensitive):

```text
RISK · ARCHITECTURE · WARNING · MISSING · SUGGESTION · NOTE
```

No other severity labels will appear in review output. If a label outside this
set appears, it is a contract violation in the review engine.

### Freshness guarantees

Context-building tools (`build_repo_context`) write to `review_engine/context/`.
These files are best-effort cache — callers must not assume they reflect the
current state of the repo without running `build_repo_context` first.

---

## 3. Side effect contract

### What mq-mcp guarantees it will never do automatically

- Commit to git
- Push to a remote
- Send network requests outside of explicitly declared API calls
  (OPENAI_API_KEY tools, `get_public_ip`, repo-signal CLI tools)
- Modify files outside `REPO_ROOT` and `MQ_MCP_ALLOWED_PATHS`
- Persist state in a location not declared in the tool docstring

### Declared persistent side effects

| Tool | Side effect | Location |
| ---- | ----------- | -------- |
| `review_file` | Saves findings | `review_engine/memory/review_history.json` |
| `build_repo_context` | Writes context + generated artifacts | `review_engine/context/`, `generated/architecture/` |
| `extract_coding_conventions` | Writes ADR file | `architecture_memory/decisions/` |
| `record_architecture_decision` | Writes ADR file | `architecture_memory/` |
| `update_repo_file` | Modifies repo file | caller-specified path |
| `edit_image` | Modifies image file | caller-specified path |
| `take_screenshot` | Writes PNG | `~/Desktop/` or caller-specified |
| `set_clipboard` | Modifies clipboard | macOS clipboard |
| `store_semantic_memory` | Writes knowledge item | `semantic_memory/store.json` |
| `bootstrap_semantic_memory` | Writes doc summaries | `semantic_memory/store.json` |
| `export_symbol_index` | Writes symbol map | `generated/symbols/symbol_index.json` |
| `risk_review_file` | Saves findings | `review_engine/memory/review_history.json` |
| `risk_review_diff` | Saves findings per file | `review_engine/memory/review_history.json` |

Any tool not listed here has no persistent side effects.

---

## 4. Context flow

```text
mq-agent
  │
  ├── invokes tool with args
  │
  ▼
mq-mcp/server.py
  │
  ├── resolve_repo_file / resolve_allowed_local_file  [path boundary]
  ├── _load_review_contract()                         [contract selection]
  ├── _load_architecture_role()                       [context: arch map]
  ├── _build_rich_cross_file_context()                [context: callgraph]
  ├── ArchitectureMemory.format_context_block()       [context: ADRs]
  ├── ReviewMemory.format_past_context()              [context: history]
  ├── ContextSelector (budget cap, priority order)    [context assembly]
  │
  ├── OpenAI API call (if applicable)
  │
  └── returns str to caller
```

Context injected into model calls, in priority order:

1. Architecture decisions (relevant ADRs from `architecture_memory/`)
2. Past review findings for this file
3. Cross-file context (related file roles, symbols, last review)
4. Architecture role (one-line label from `architecture_map.json`)

The caller does not control context selection. mq-mcp owns context assembly.

---

## 5. Cross-repo contracts

These define what mq-mcp expects from each ecosystem partner and what it
provides back. These contracts are currently documented in prose; v1.3.0
makes them explicit and verifiable.

### mq-agent → mq-mcp

mq-agent is the orchestration layer. It may:

- Discover tools via MCP protocol
- Invoke any Class A/B tool without approval gates
- Invoke Class C/D tools only after presenting the tool's safety_notes to the user
- Read `tool_safety_report` to display safety classification
- Route review and architecture analysis requests to mq-mcp tools

mq-agent must not:

- Reimplement review logic locally
- Construct filesystem paths outside of tool arguments
- Assume mq-mcp maintains session state between calls
- Invoke tools in a sequence that collectively produces a git commit

### repo-signal → mq-mcp

repo-signal provides read-only repository intelligence:

- `repo_signal_analyze` / `repo_signal_checklist` / `repo_signal_inspect` /
  `repo_signal_doctor_json` — mq-mcp proxies these as Class B tools
- Expected output: structured text or JSON from repo-signal CLI
- repo-signal v1.1.0+ writes packs to `.repo-signal/exports/`;
  `callgraph_builder._try_merge_repo_signal_packs()` merges them automatically

mq-mcp must not: duplicate repo-signal's graph-building logic.

### mq-hal → mq-mcp

mq-hal provides runtime and model health summaries:

- `hal_repo_report` — mq-mcp proxies as Class D (runs mq-hal CLI)
- Expected output: text report from mq-hal

### mq-image-analyze → mq-mcp

mq-image-analyze provides visual analysis:

- Invoked as an external tool; output is a structured JSON blob (`visual_architecture_observation.v1`)
- mq-mcp does not call mq-image-analyze directly — callers invoke it and pass
  the result as context to mq-mcp review tools

### mq-mcp → callers (output contract)

mq-mcp guarantees to callers:

- All tool output is a `str`
- Error output begins with `{tool_name} failed:` or `ERROR:`
- Review output uses the fixed severity vocabulary
- No output contains API keys, tokens, or local machine paths in cleartext
- Tool names are stable across patch versions; breaking renames require a minor bump

---

## 6. Profile access model

Each profile in `profiles/` declares a `recommended_tools` list that restricts
which tools the profile's client should invoke. Profiles are not enforcement
mechanisms — they are guidance. Enforcement is the client's responsibility.

| Profile | Intended caller | Max tool class |
| ------- | --------------- | -------------- |
| `read-only.json` | Any read-only client | A |
| `repo-only.json` | Repo-focused client | A/C |
| `claude-desktop.json` | Claude Desktop | A/B |
| `codex.json` | OpenAI Codex | A/B |
| `openai-bridge.json` | OpenAI bridge | A/B |
| `developer.json` | Local developer | A/B/C/D |
| `local-macos.json` | Local macOS workflows | A/B/C/D |
| `mq-agent.json` | mq-agent orchestrator | A/B |

`validate_orchestration_contract` checks that profiles declaring a max class
do not include tools above that class in their `recommended_tools`.

---

## 7. Guarantees

The following are always true regardless of tool, caller, or configuration:

1. No tool reads or writes outside `REPO_ROOT` unless `MQ_MCP_ALLOWED_PATHS` is set
2. No tool executes a dynamically-constructed shell command
3. No tool commits or pushes git state
4. No tool output contains redactable secrets in cleartext
5. All tool names registered in `@mcp.tool()` appear in `docs/TOOL_SAFETY.md`
6. All tools with `write: true` or `subprocess: true` in `tool_contracts.json`
   are classified Class C or D. `write: true` is allowed for Class D subprocess
   tools when the subprocess may create local artifacts, such as diagnostic
   bundles.
7. Class C learn/bootstrap tools may be intentionally profile-free because they
   are user-invoked write operations, not automated profile defaults.
8. Every tool call is stateless with respect to prior calls — no implicit session

These guarantees are verified by `validate_orchestration_contract` and
`detect_architecture_drift`.

---

## 8. WARN acceptance policy

`validate_orchestration_contract` and `detect_architecture_drift` emit `[WARN]`
findings that do not block a release but signal potential drift.

### When a WARN is acceptable

| WARN | Acceptable when |
| ---- | --------------- |
| `ORCHESTRATION_CONTRACT.md older than server.py` | No new `@mcp.tool()` functions were added in the commits since the last contract update. The diff-aware message confirms this by listing no new tools. |
| `RUNTIME_CONTRACT.md older than server.py` | The changes to `server.py` were internal helpers, refactors, or bug fixes that do not affect the declared guarantees or tool surface. |
| `architecture_map.json older than server.py` | `build_repo_context()` has not been re-run since the last server.py change. Acceptable in development; run before a review or release. |

### When a WARN requires action

- WARN lists specific tool names as "new tools since last contract update" → update the contract.
- WARN fires after adding a new tool class or safety boundary → update `RUNTIME_CONTRACT.md`.
- WARN persists across multiple commits with new tools → treat as FAIL for release purposes.

The release gate (`scripts/release-check.sh`) does not block on WARNs, but
they should be reviewed and resolved before tagging a release.
