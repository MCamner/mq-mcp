# Global Architecture Notes

## System overview

```
User (zsh terminal on macOS)
├── mqlaunch (macos-scripts TUI)
│   ├── ask / bridget → mq-mcp
│   ├── release-check, doctor, scan → macos-scripts tools
│   └── repo-signal commands → repo-signal CLI
│
├── bridget (mq-mcp bridge)
│   └── OpenAI Chat API + local MCP server (server.py)
│
├── ask (mq-mcp vector Q&A)
│   └── OpenAI Responses API + vector store
│
└── repo-signal CLI
    ├── analyze, doctor, publish-checklist → local repo scanning
    ├── repoaware → AI-powered analysis
    └── semantic-upload → vector store management
```

## AI layer

| Layer | Tool | API | Model |
|---|---|---|---|
| Live tools | bridget | OpenAI Chat Completions + MCP | gpt-5.4-mini |
| Vector Q&A | ask | OpenAI Responses API | gpt-5.4-mini |
| Repo analysis | repo-signal repoaware | OpenAI Chat | configurable |
| Repo upload | repo-signal semantic-upload | OpenAI Files + Vector Stores | n/a |

## Vector stores

| Store | ID | Contents | Used by |
|---|---|---|---|
| `mq-mcp-repo-knowledge` | vs_6a0513bc... | mq-mcp repo files only | `ask` CLI, `bridget --search` |
| `semantic repository memory` | vs_69ffa9a4... | All repos (global high-signal) | global AI assistant |
| `macos-scripts-knowledge` | vs_69f93de1... | macos-scripts repo | macos-scripts tooling |
| `mcamner-journal-knowledge` | vs_69fd0b6b... | journal content | journal tools |

## MCP architecture

`server.py` is a FastMCP server with 13 tools sandboxed to `~/mq-mcp`.
`bridge.py` spawns it as a subprocess via stdio and proxies tool calls to OpenAI.

Tool safety tiers:
- Read-only: get_system_resources, read_repo_file, list_repo_files, search_repo, git_status, git_diff, analyze_csv, analyze_guitar_pro
- Write: update_repo_file, edit_image
- Execution: validate_project, run_mqlaunch, open_in_app

## Env management

Secrets live in per-project `.env` files.
`direnv` loads them automatically when entering the project dir.
`mq-mcp/.env` is the primary: OPENAI_API_KEY, OPENAI_VECTOR_STORE_ID, OPENAI_MODEL.

## Runtime environment

- macOS (darwin, arm64)
- Python 3.11+ via uv
- zsh 5.9 with autosuggestions, syntax-highlighting, fzf, zoxide
- Homebrew for system tools (eza, bat, btop, etc.)
