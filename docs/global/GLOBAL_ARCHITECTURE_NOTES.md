# Global Architecture Notes

## System overview

```text
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

`server.py` is a FastMCP server with 50 tools. Repo tools are sandboxed to `~/mq-mcp` via `resolve_repo_file()`. External tools use `resolve_allowed_local_file()` gated by `MQ_MCP_ALLOWED_PATHS`.
`bridge.py` spawns it as a subprocess via stdio and proxies tool calls to OpenAI.

Tool safety tiers (see docs/TOOL_SAFETY.md for full classification):

- Class A — Read-only, repo-scoped: read_repo_file, list_repo_files, search_repo, git_status, git_diff, analyze_csv, tool_safety_report, list_local_repos, list_openable_apps
- Class B — Read-only, external access: get_system_resources, repo_signal_*, get_clipboard, get_wifi_info, get_battery_status, list_running_apps, get_todays_events, find_large_files, find_recent_files, check_port, get_public_ip, analyze_guitar_pro
- Class C — Write-capable: update_repo_file, edit_image, set_clipboard, take_screenshot
- Class D — Subprocess/open-app: open_in_app, validate_project, run_mqlaunch, open_repo_terminal, hal_repo_report, open_messages, open_finder, open_url, show_notification, open_app, speak_text, open_chrome, open_spotify, open_terminal, open_vscode, set_volume, toggle_dark_mode, lock_screen, create_note, set_reminder, set_wallpaper, run_tests
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
