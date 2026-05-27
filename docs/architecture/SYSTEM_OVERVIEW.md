# mq-mcp System Overview

This document is the ground-truth architecture reference for mq-mcp.
The review engine uses it for architecture drift detection.
Last updated: 2026-05-27.

---

## What mq-mcp is

mq-mcp is a local-first AI engineering runtime built on the Model Context
Protocol (MCP). It exposes a controlled, documented, and testable MCP surface
that can be consumed by local agents, OpenAI bridge workflows, and MCP clients
such as Claude Desktop.

It is not an unrestricted remote-control layer.
It is not a cloud service.
It does not store data outside the local machine.

---

## Runtime layers

```text
┌─────────────────────────────────────────────┐
│  MCP clients                                │
│  Claude Desktop · mq-agent · mqlaunch       │
└──────────────────────┬──────────────────────┘
                       │ MCP protocol (stdio / HTTP+SSE)
┌──────────────────────▼──────────────────────┐
│  mq-mcp/server.py — MCP server              │
│  Tool registry · HTTP endpoints · safety    │
└──────────────────────┬──────────────────────┘
                       │ direct Python import
┌──────────────────────▼──────────────────────┐
│  mq-mcp/bridge.py — OpenAI bridge           │
│  Prompt routing · tool dispatch · Bridget   │
└──────┬───────────────┬──────────────────────┘
       │               │
┌──────▼──────┐  ┌─────▼──────────────────────┐
│  ask.py     │  │  review_engine/             │
│  vector     │  │  repo_context_builder.py    │
│  store      │  │  review_router.py           │
│  querying   │  │  severity_engine.py         │
└─────────────┘  └────────────────────────────┘
```

---

## File responsibilities

### `mq-mcp/server.py`

**Role:** MCP server — tool registry and HTTP endpoints.

Owns:

- All `@mcp.tool()` definitions (53 tools as of v1.1)
- HTTP health, diagnostics, and tool-contract endpoints
- Path safety: `resolve_repo_file`, `resolve_allowed_local_file`
- Repo registry: `known_local_repos`, `allowed_external_roots`
- Review engine MCP surface: `review_file`, `build_repo_context`,
  `list_review_contracts`

Does not own:

- Prompt routing or OpenAI API calls (→ bridge.py)
- Semantic memory queries (→ ask.py)
- Review engine logic (→ review_engine/)

### `mq-mcp/bridge.py`

**Role:** Orchestration layer — MCP ↔ LLM bridge.

Owns:

- CLI argument parsing (`parse_prompt`)
- Bridget identity rendering (`show_bridget_face`, `scramble_print`)
- Voice command routing (`handle_voice_command`)
- Repo navigation (`handle_goto_repo`, `is_goto_repo_prompt`)
- OpenAI API client instantiation and message loop
- MCP tool dispatch during a bridge session

Does not own:

- MCP tool definitions (→ server.py)
- Vector store queries (→ ask.py)
- Repo context building (→ review_engine/)

### `mq-mcp/ask.py`

**Role:** Semantic memory — vector store querying.

Owns:

- OpenAI `file_search` API calls against local and global vector stores
- Local repo memory (`OPENAI_VECTOR_STORE_ID`)
- Global semantic memory (`OPENAI_SEMANTIC_MEMORY_ID`)
- CLI entry point for standalone `ask` invocations

### `mq-mcp/bridget_voice.py`

**Role:** Voice command handler — TTS and voice triggers.

Owns:

- macOS `say` command integration
- Voice enable/disable toggle
- Voice command keyword detection

### `review_engine/repo_context_builder.py`

**Role:** Static context generator for the review engine.

Owns:

- Architecture role heuristics (file → role label)
- Python AST symbol extraction (functions, classes, constants, docstrings)
- Output: `review_engine/context/architecture_map.json`
- Output: `review_engine/context/file_summary_index.json`

### `review_engine/review_router.py`

**Role:** Skill router — maps files to review skills.

Owns:

- Extension-based routing (`.py`, `.sh`)
- Path-based routing (`server.py` → mcp-tool skill)
- Skill file loading from `reviews/skills/`

### `review_engine/severity_engine.py`

**Role:** Review output parser and formatter.

Owns:

- `[SEVERITY] file:line\nbody` block parsing
- Severity ordering (RISK → ARCHITECTURE → WARNING → MISSING → SUGGESTION → NOTE)
- Structured `Finding` dataclass
- Summary formatting and blocking-finding detection

---

## Review engine pipeline

```text
review_file(path, mode)
  │
  ├── resolve_repo_file(path)          [safety boundary]
  ├── _load_review_contract(mode)      [reviews/contracts/]
  ├── _load_architecture_role(path)    [review_engine/context/]
  ├── review_router.route_file(path)   [reviews/skills/]
  │
  ├── OpenAI chat.completions.create() [model call]
  │     system = contract + skill
  │     user   = file content + arch role
  │
  └── severity_engine.parse_findings() [structured output]
        → format_summary()
```

---

## Path safety model

Two resolvers enforce filesystem boundaries:

| Resolver | Accepts | Rejects |
| --- | --- | --- |
| `resolve_repo_file` | Repo-relative paths inside `REPO_ROOT` | Anything outside repo |
| `resolve_allowed_local_file` | Repo paths + `MQ_MCP_ALLOWED_PATHS` roots | Anything outside allowed roots |

`REPO_ROOT` is always `Path(__file__).resolve().parent.parent` from server.py.

Tools that should only touch the repo use `resolve_repo_file`.
Tools that need broader access (Guitar Pro, image editor, open-in-app)
use `resolve_allowed_local_file`.

---

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API access | required |
| `OPENAI_MODEL` | Model for bridge and review | `gpt-4.1-mini` |
| `OPENAI_VECTOR_STORE_ID` | Local repo semantic memory | — |
| `OPENAI_SEMANTIC_MEMORY_ID` | Global cross-repo memory | — |
| `MQ_MCP_HOST` | MCP server bind host | `127.0.0.1` |
| `MQ_MCP_PORT` | MCP server bind port | `8765` |
| `MQ_MCP_LOCAL_REPOS` | Comma-separated extra repo paths | — |
| `MQ_MCP_ALLOWED_PATHS` | Colon-separated extra allowed roots | — |
| `MQ_MCP_REQUEST_LOG` | Enable request logging | off |
| `MQ_MCP_SERVER_COMMAND` | Bridge server launch command | `uv` |
| `MQ_MCP_SERVER_ARGS` | Bridge server launch args | `run mcp run server.py` |

---

## Tool safety classes

| Class | Meaning |
| --- | --- |
| A | Read-only, repo-scoped |
| B | Read-only, allowed external paths or system reads |
| C | Write-capable, controlled scope |
| D | Subprocess / open-app |

Full classification in `docs/TOOL_SAFETY.md`.

---

## What this system is NOT

- Not a web service — runs only on localhost
- Not a persistent daemon by default — started explicitly
- Not an autonomous agent — tools require explicit invocation
- Not a secret store — API keys come from `.env`, never from tool output
- Not a code execution sandbox — subprocess tools have a fixed allowlist
