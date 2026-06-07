# MCP Tool Safety Classification

This document classifies all 115 tools exposed by `mq-mcp/server.py` by what they are
allowed to do, what they cannot do, and which path resolver they use.

## Resolvers

Two path resolvers enforce access boundaries:

| Resolver | Accepts | Rejects |
| --- | --- | --- |
| `resolve_repo_file(path)` | Repo-relative paths inside `REPO_ROOT` | Absolute paths, `../` traversal, anything outside repo |
| `resolve_allowed_local_file(path)` | Repo-relative paths + absolute paths within `MQ_MCP_ALLOWED_PATHS` | Anything outside repo and all allowed roots |

`REPO_ROOT` is always included in `resolve_allowed_local_file` — no configuration needed for repo files.

---

## Class A — Read-only, repo-scoped

These tools cannot write files, cannot run processes, and cannot access anything outside the repository root.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `read_repo_file` | Read any file inside the repo | Write, delete, access outside repo |
| `list_repo_files` | Walk and list repo file tree | Write, delete, show ignored/hidden dirs |
| `search_repo` | Run `git grep -n` inside repo | Write, access outside repo |
| `git_status` | Show branch, status, last 5 commits | Modify git state |
| `git_diff` | Show diff for repo or a specific file | Modify git state |
| `release_gate_run` | Run Release Gate v2 deterministic validation | Write, modify repo |
| `analyze_csv` | Read and summarize a CSV inside repo | Write, access outside repo |
| `tool_safety_report` | Return contents of docs/TOOL_SAFETY.md | Write, access outside repo |
| `list_local_repos` | List registered repos from MQ_MCP_LOCAL_REPOS | Write, access outside repo |
| `list_openable_apps` | Return static list of apps Bridget can open | Write, subprocess, file access |
| `list_review_contracts` | List available review contracts from reviews/contracts/ | Write, access outside repo |
| `review_file` | Run AI review on a repo file using a review contract | Write, modify code; calls OpenAI API |
| `build_repo_context` | Rebuild architecture_map.json and file_summary_index.json | Write outside repo, modify repo files |
| `list_review_history` | List all files with review history and last review summary | Write, access outside repo |
| `get_last_review` | Return last review findings for a repo file from local memory | Write, access outside repo |
| `detect_architecture_drift` | Detect drift between declared docs and actual runtime state | Write, access outside repo |
| `review_diff` | Review git-changed files using review_file | Write, modify code; calls git + OpenAI API |
| `review_repo` | Review least-recently-reviewed repo files using review_file | Write, modify code; calls OpenAI API |
| `review_runtime_contract` | Verify RUNTIME_CONTRACT.md claims against actual server state | Write, modify server |
| `validate_orchestration_contract` | Verify tool set satisfies orchestration contract (profiles, classes, error prefixes) | Write, commit, network |
| `list_architecture_docs` | List docs/architecture/ files with freshness status relative to server.py | Write, access outside repo |
| `review_architecture_doc` | Apply architecture review contract to a named architecture document | Write, modify docs; calls OpenAI API |
| `list_architecture_decisions` | List all architecture memory entries (ADRs, boundaries, philosophy, rejected) | Write, access outside repo |
| `get_architecture_decision` | Return full text of a specific architecture memory entry by ID | Write, access outside repo |
| `search_semantic_memory` | Search semantic memory by keywords | Write, modify memory store |
| `get_semantic_memory` | Return full content of a semantic memory item by key | Write, modify memory store |
| `list_semantic_memory` | List all semantic memory items with previews | Write, modify memory store |
| `repo_signal_status` | Report whether repo-signal export packs are present and merged | Write, modify packs |
| `risk_review_file` | Targeted risk pass (security/risk/architecture) with grep pre-scan + AI review | Write, commit, network |
| `risk_review_diff` | Risk pass over changed files in working tree or staging area | Write, commit, network |
| `list_review_skills` | List available review skills, path-prefix routes, and extension routes | Write, commit |
| `list_learnings` | List stored engineering lessons with optional filters | Write, network |
| `get_learning` | Return a single lesson by id prefix | Write, network |
| `explain_learned_pattern` | Compatibility alias for `get_learning` | Write, network |
| `search_learnings` | Full-text search across stored lessons | Write, network |
| `search_learned_patterns` | Compatibility alias for `search_learnings` | Write, network |
| `summarize_learnings` | Summarize lessons by source and risk | Write, network |
| `learn_hygiene` | Report learn memory hygiene | Write, network |
| `promote_learning` | Preview how a lesson would look in a target doc (no file writes) | Write any file, commit, execute |
| `learning_status` | Return learn layer stats: counts by source, risk, and repo | Write, network |
| `learn_status` | Compatibility alias for `learning_status` | Write, network |

Resolver: `resolve_repo_file` (git_status and git_diff use `run_repo_command` with `cwd=REPO_ROOT`); `list_openable_apps` uses no resolver (static output only)

---

## Class B — Read-only, allowed external paths

These tools cannot write files and cannot run processes. They can read files outside the repo if `MQ_MCP_ALLOWED_PATHS` is configured.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `get_system_resources` | Read CPU, memory, disk stats via psutil | Write, access files |
| `analyze_guitar_pro` | Parse GP3/GP4/GP5 files in repo or allowed roots | Write, access outside allowed roots |
| `repo_signal_analyze` | Run repo-signal analyze on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_checklist` | Run repo-signal publish checklist on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_inspect` | Run repo-signal inspect --json on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_doctor_json` | Run repo-signal doctor --json on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_report` | Run repo-signal report --format json on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_suggest` | Run repo-signal suggest --format json on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_positioning` | Run repo-signal positioning --json on an allowed repo path | Write, access outside allowed roots |
| `zephyr_validate` | Validate a zephyr architecture YAML file | Write, access outside allowed roots |
| `zephyr_review` | Review a zephyr architecture YAML file | Write, access outside allowed roots |
| `zephyr_analyze` | Analyze a zephyr architecture YAML file | Write, access outside allowed roots |
| `zephyr_diff` | Compare two zephyr architecture YAML files | Write, access outside allowed roots |
| `image_observe_architecture` | Observe an architecture diagram through mq-image | Write, access outside allowed roots |
| `image_analyze_ui` | Analyze a UI screenshot through mq-image | Write, access outside allowed roots |
| `image_analyze` | Analyze an image through mq-image | Write, access outside allowed roots |
| `ums_command_catalog` | Read the mq-ums command catalog from MQ_UMS_DIR/config | Write, subprocess, network |
| `ums_audit_log` | Read mq-ums local audit logs from MQ_UMS_DIR/logs | Write, subprocess, network |
| `get_clipboard` | Read clipboard via pbpaste | Write, access files |
| `get_wifi_info` | Read Wi-Fi info via airport/networksetup | Write, access files |
| `get_battery_status` | Read battery status via pmset | Write, access files |
| `list_running_apps` | List visible running apps via osascript | Write, access files |
| `get_todays_events` | Read today's Calendar events via osascript | Write, access files |
| `find_large_files` | Find files over a size threshold via find | Write, access files |
| `find_recent_files` | Find recently modified files via find | Write, access files |
| `check_port` | Check if a TCP port is in use via lsof | Write, access files |
| `get_public_ip` | Return public IP via curl to api.ipify.org | Write, access files; makes external HTTP call |
| `ollama_learn_status` | Check local Ollama server and mq-learn model availability | Write, subprocess |
| `ollama_learn_extract` | Dry-run extraction of a learn pattern via local Ollama | Write, subprocess |
| `learn_extract_from_last_review` | Dry-run extraction from the last stored review for a file | Write, subprocess |

Resolver: `resolve_allowed_local_file` (repo-signal tools, analyze_guitar_pro); no resolver for system read-only tools (they read system state, not user files)

---

## Class C — Write-capable, controlled scope

These tools can modify files on disk. They are scoped to the repo or explicitly allowed paths.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `update_repo_file` | Replace exact text in allowed repo files | Write outside repo, commit, auto-delete, binary files |
| `edit_image` | Rotate or convert images in repo or allowed roots | Write outside allowed roots, commit, delete |
| `set_clipboard` | Copy text to the macOS clipboard via pbcopy | Access files, run arbitrary commands |
| `take_screenshot` | Capture screen to a file (default ~/Desktop/screenshot.png) | Access outside ~/Desktop or given path |
| `record_architecture_decision` | Append a new ADR entry to architecture_memory/ | Write outside repo, commit, overwrite existing entries |
| `extract_coding_conventions` | Extract conventions from last review and persist to architecture_memory/ | Write outside repo, commit; requires OPENAI_API_KEY |
| `store_semantic_memory` | Store or update a knowledge item in semantic_memory/store.json | Write outside repo, commit |
| `bootstrap_semantic_memory` | Ingest key mq-mcp docs into semantic memory | Write outside repo, commit |
| `export_symbol_index` | Write callgraph symbol map to generated/symbols/symbol_index.json | Write outside repo, commit |
| `record_learning` | Append a verified lesson to REPO_ROOT/learn_engine/memory/lessons.jsonl | Write outside repo, commit, execute; secrets are redacted before write |
| `learn_from_review` | Create a learning record from the last review findings for a file | Write outside repo, commit |
| `learn_from_diff` | Create a learning record with current git diff as context | Write outside repo, commit |
| `bootstrap_learning_memory` | Seed the learn layer from architecture memory ADRs | Write outside repo, commit |

`update_repo_file` has additional guards: blocked filenames (`.env`, `uv.lock`), blocked directories (`.git`, `.venv`), allowed suffixes only, exact-match required, refuses ambiguous matches, never commits.

Resolver: `resolve_repo_file` (update_repo_file, record_architecture_decision), `resolve_allowed_local_file` (edit_image)

---

## Class D — Subprocess / open-app

These tools invoke external processes or open applications. Review carefully before extending.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `open_in_app` | Open a file in its default macOS app | Accepts only repo or allowed-root paths |
| `validate_project` | Run `scripts/validate.sh` with a 60s timeout | Run arbitrary commands |
| `run_mqlaunch` | Open `mqlaunch.sh` in a new Terminal window via osascript | — |
| `open_repo_terminal` | Open a registered repo in a new Terminal window | Write files |
| `hal_repo_report` | Run a read-only mq-hal report (audit, brief, release-brief, repo-status, ci) | Write files, run arbitrary commands |
| `open_messages` | Open Messages.app, optionally to a contact | Send messages, write files |
| `open_finder` | Open Finder at a path | Write files |
| `open_url` | Open a URL in the default browser | Arbitrary HTTP; URL must start with http:// or https:// |
| `show_notification` | Send a macOS system notification via osascript | Write files, access files |
| `open_app` | Launch any macOS application by name | Arbitrary process launch; rejects names containing `/` |
| `speak_text` | Speak text aloud via macOS `say` command | Write files, record audio |
| `open_chrome` | Open Google Chrome, optionally to a URL | Arbitrary HTTP; URL validated |
| `open_spotify` | Open Spotify, optionally to URI or search | Spotify URIs only or search query |
| `open_terminal` | Open a new Terminal window, optionally at a path | Run arbitrary commands in Terminal |
| `open_vscode` | Open VS Code, optionally at a file or folder | Arbitrary file access via VS Code |
| `set_volume` | Set macOS output volume (0–100) via osascript | Access files |
| `toggle_dark_mode` | Toggle macOS dark/light mode via osascript | Access files |
| `lock_screen` | Lock the macOS screen via osascript keystroke | Access files |
| `create_note` | Create a new note in Notes.app via osascript | Arbitrary note content; cannot read back |
| `set_reminder` | Create a reminder in Reminders.app via osascript | Arbitrary reminder content |
| `set_wallpaper` | Set macOS desktop wallpaper via osascript | Accepts any absolute image path |
| `run_tests` | Run pytest in a registered local repository | Execute code in registered repo |
| `run_mqlaunch_doctor` | Run `mqlaunch doctor` — env/dependency health report | Write files, network |
| `run_mqlaunch_selftest` | Run `mqlaunch selftest` — internal smoke tests | Write files, network |
| `run_mqlaunch_release_check` | Run `mqlaunch release-check` — pre-release gate | Write files, network |
| `run_mqlaunch_version` | Run `mqlaunch version` — version info (TUI; limited headless) | Write files |
| `run_mqlaunch_system_check` | Run `mqlaunch system check` — system overview (TUI; limited headless) | Write files |
| `run_mqlaunch_perf` | Run `mqlaunch perf` — performance menu (TUI; no parseable output headless) | Write files |
| `run_mqlaunch_demo` | Run `mqlaunch demo` — guided demo (TUI; interactive; no output headless) | Write files |
| `run_mqlaunch_bundle` | Run `mqlaunch bundle` — debug bundle (TUI; bundle NOT created headless) | Arbitrary file writes |
| `run_mqlaunch_ask` | Ask mqlaunch a question (requires OPENAI_API_KEY; clipboard fallback otherwise) | Write files; falls back silently without API key |

Resolver: `resolve_allowed_local_file` (open_in_app), fixed script path (validate_project, run_mqlaunch), MQ_MCP_LOCAL_REPOS (open_repo_terminal, run_tests), fixed allowlist (hal_repo_report), validated URL prefix (open_url, open_chrome), validated app name (open_app), no resolver (open_messages, show_notification, speak_text, set_volume, toggle_dark_mode, lock_screen, create_note, set_reminder, set_wallpaper), open path (open_terminal, open_vscode, open_finder, take_screenshot, find_large_files, find_recent_files, get_public_ip)

---

## Summary table

| Tool | Class | Resolver | Write | Subprocess |
| --- | --- | --- | --- | --- |
| `read_repo_file` | A | resolve_repo_file | No | No |
| `list_repo_files` | A | REPO_ROOT walk | No | No |
| `search_repo` | A | git grep (cwd=REPO_ROOT) | No | No |
| `git_status` | A | run_repo_command | No | No |
| `git_diff` | A | run_repo_command | No | No |
| `analyze_csv` | A | resolve_repo_file | No | No |
| `tool_safety_report` | A | REPO_ROOT (fixed path) | No | No |
| `list_local_repos` | A | MQ_MCP_LOCAL_REPOS (read env) | No | No |
| `list_openable_apps` | A | none (static output) | No | No |
| `get_system_resources` | B | psutil (no file path) | No | No |
| `analyze_guitar_pro` | B | resolve_allowed_local_file | No | No |
| `repo_signal_analyze` | B | resolve_allowed_local_file | No | Yes |
| `repo_signal_checklist` | B | resolve_allowed_local_file | No | Yes |
| `repo_signal_inspect` | B | resolve_allowed_local_file | No | Yes |
| `repo_signal_doctor_json` | B | resolve_allowed_local_file | No | Yes |
| `repo_signal_report` | B | resolve_allowed_local_file | No | Yes |
| `repo_signal_suggest` | B | resolve_allowed_local_file | No | Yes |
| `repo_signal_positioning` | B | resolve_allowed_local_file | No | Yes |
| `zephyr_validate` | B | resolve_allowed_local_file | No | Yes |
| `zephyr_review` | B | resolve_allowed_local_file | No | Yes |
| `zephyr_analyze` | B | resolve_allowed_local_file | No | Yes |
| `zephyr_diff` | B | resolve_allowed_local_file | No | Yes |
| `image_observe_architecture` | B | resolve_allowed_local_file | No | Yes |
| `image_analyze_ui` | B | resolve_allowed_local_file | No | Yes |
| `image_analyze` | B | resolve_allowed_local_file | No | Yes |
| `ums_command_catalog` | B | MQ_UMS_DIR | No | No |
| `ums_audit_log` | B | MQ_UMS_DIR | No | No |
| `get_clipboard` | B | none (pbpaste) | No | Yes |
| `get_wifi_info` | B | none (airport/networksetup) | No | Yes |
| `get_battery_status` | B | none (pmset) | No | Yes |
| `list_running_apps` | B | none (osascript) | No | Yes |
| `get_todays_events` | B | none (osascript/Calendar) | No | Yes |
| `find_large_files` | B | open path (no resolver) | No | Yes |
| `find_recent_files` | B | open path (no resolver) | No | Yes |
| `check_port` | B | none (lsof) | No | Yes |
| `get_public_ip` | B | none (curl to api.ipify.org) | No | Yes |
| `update_repo_file` | C | resolve_repo_file | Yes | No |
| `edit_image` | C | resolve_allowed_local_file | Yes | No |
| `set_clipboard` | C | none (pbcopy) | Clipboard | Yes |
| `take_screenshot` | C | open path (default ~/Desktop) | Yes (file) | Yes |
| `open_in_app` | D | resolve_allowed_local_file | No | Yes |
| `validate_project` | D | fixed path | No | Yes |
| `run_mqlaunch` | D | fixed path | Potentially | Yes |
| `open_repo_terminal` | D | MQ_MCP_LOCAL_REPOS (fixed paths) | No | Yes |
| `hal_repo_report` | D | fixed allowlist (mq-hal CLI) | No | Yes |
| `open_messages` | D | none | No | Yes |
| `open_finder` | D | open path | No | Yes |
| `open_url` | D | URL prefix validation | No | Yes |
| `show_notification` | D | none | No | Yes |
| `open_app` | D | name validation (no `/`) | No | Yes |
| `speak_text` | D | none | No | Yes |
| `open_chrome` | D | URL prefix validation | No | Yes |
| `open_spotify` | D | URI/search validation | No | Yes |
| `open_terminal` | D | open path | No | Yes |
| `open_vscode` | D | open path | No | Yes |
| `set_volume` | D | none | No | Yes |
| `toggle_dark_mode` | D | none | No | Yes |
| `lock_screen` | D | none | No | Yes |
| `create_note` | D | none | No | Yes |
| `set_reminder` | D | none | No | Yes |
| `set_wallpaper` | D | open path | No | Yes |
| `run_tests` | D | MQ_MCP_LOCAL_REPOS (fixed paths) | No | Yes |
| `list_review_contracts` | A | REPO_ROOT (fixed path) | No | No |
| `review_file` | A | resolve_repo_file | No | No (OpenAI API) |
| `build_repo_context` | D | fixed script path | No | Yes |
| `list_review_history` | A | REPO_ROOT (fixed path) | No | No |
| `get_last_review` | A | REPO_ROOT (fixed path) | No | No |
| `detect_architecture_drift` | A | REPO_ROOT (AST + file reads) | No | No |
| `review_diff` | A | resolve_repo_file (per file) | No | No (git + OpenAI API) |
| `review_repo` | A | REPO_ROOT walk + resolve_repo_file | No | No (OpenAI API) |
| `review_runtime_contract` | A | REPO_ROOT (reads contract + server.py) | No | No (OpenAI API) |
| `validate_orchestration_contract` | A | REPO_ROOT (reads contract, profiles, server.py) | No | No |
| `list_architecture_docs` | A | REPO_ROOT/docs/architecture/ | No | No |
| `review_architecture_doc` | A | REPO_ROOT/docs/architecture/ + server.py | No | No (OpenAI API) |
| `list_architecture_decisions` | A | REPO_ROOT/architecture_memory/ | No | No |
| `get_architecture_decision` | A | REPO_ROOT/architecture_memory/ | No | No |
| `record_architecture_decision` | C | REPO_ROOT/architecture_memory/ | Yes | No |
| `extract_coding_conventions` | C | REPO_ROOT/architecture_memory/ + review memory | Yes | No (OpenAI API) |
| `search_semantic_memory` | A | REPO_ROOT/semantic_memory/store.json | No | No |
| `get_semantic_memory` | A | REPO_ROOT/semantic_memory/store.json | No | No |
| `list_semantic_memory` | A | REPO_ROOT/semantic_memory/store.json | No | No |
| `store_semantic_memory` | C | REPO_ROOT/semantic_memory/store.json | Yes | No |
| `bootstrap_semantic_memory` | C | REPO_ROOT/semantic_memory/store.json + docs | Yes | No |
| `export_symbol_index` | C | REPO_ROOT/generated/symbols/symbol_index.json | Yes | No |
| `repo_signal_status` | A | REPO_ROOT/.repo-signal/exports/ (read-only) | No | No |
| `risk_review_file` | A | REPO_ROOT (reads file) + review_engine/memory/ | No | No (OpenAI API) |
| `risk_review_diff` | A | REPO_ROOT (reads diff) + review_engine/memory/ | No | No (OpenAI API) |
| `release_gate_run` | A | REPO_ROOT (release gate checks) | No | No |
| `list_review_skills` | A | REPO_ROOT/reviews/skills/ (read-only) | No | No |
| `record_learning` | C | REPO_ROOT/learn_engine/memory/lessons.jsonl | Yes | No |
| `learn_from_review` | C | REPO_ROOT/learn_engine/memory/lessons.jsonl | Yes | No |
| `learn_from_diff` | C | REPO_ROOT/learn_engine/memory/lessons.jsonl | Yes | No |
| `bootstrap_learning_memory` | C | REPO_ROOT/learn_engine/memory/lessons.jsonl | Yes | No |
| `list_learnings` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl | No | No |
| `get_learning` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl | No | No |
| `explain_learned_pattern` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl | No | No |
| `search_learnings` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl | No | No |
| `search_learned_patterns` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl | No | No |
| `summarize_learnings` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl | No | No |
| `learn_hygiene` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl (read) | No | No |
| `promote_learning` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl (read) | No | No |
| `learning_status` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl (read) | No | No |
| `learn_status` | A | REPO_ROOT/learn_engine/memory/lessons.jsonl (read) | No | No |
| `ollama_learn_status` | B | http://localhost:11434/api/tags (read) | No | No |
| `ollama_learn_extract` | B | http://localhost:11434/api/generate (read) | No | No |
| `learn_extract_from_last_review` | B | review_memory (read) + http://localhost:11434/api/generate (read) | No | No |
| `run_mqlaunch_doctor` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_selftest` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_release_check` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_version` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_system_check` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_perf` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_demo` | D | subprocess (mqlaunch) | No | Yes |
| `run_mqlaunch_bundle` | D | subprocess (mqlaunch) | Yes | Yes |
| `run_mqlaunch_ask` | D | subprocess (mqlaunch) + OpenAI API | No | Yes |
