# MCP Tool Inventory

50 tools exposed by `mq-mcp/server.py`.

For full safety classification, resolvers, and per-tool access boundaries
see [`TOOL_SAFETY.md`](TOOL_SAFETY.md).

---

## Class A — Read-only, repo-scoped

Cannot write files, cannot run processes, cannot access outside repo root.

| Tool | Resolver | Description |
| --- | --- | --- |
| `read_repo_file` | `resolve_repo_file` | Read any file inside the repo |
| `list_repo_files` | (none — os.walk inside root) | List repo files up to a depth |
| `search_repo` | `run_repo_command` | Full-text search via git grep |
| `git_status` | `run_repo_command` | Branch, status, last 5 commits |
| `git_diff` | `run_repo_command` | Diff for repo or a specific path |
| `analyze_csv` | `resolve_repo_file` | Summarize a CSV inside the repo |
| `tool_safety_report` | (none — reads docs/TOOL_SAFETY.md) | Return tool safety classification |
| `list_local_repos` | (none — reads env var) | List repos from MQ_MCP_LOCAL_REPOS |
| `list_openable_apps` | (none — static output) | List apps Bridget can open |

---

## Class B — Read-only, allowed external paths

Cannot write files. Can read outside the repo if MQ_MCP_ALLOWED_PATHS is set.

| Tool | Resolver | Description |
| --- | --- | --- |
| `get_system_resources` | (none — psutil) | CPU, memory, disk stats |
| `analyze_guitar_pro` | `resolve_allowed_local_file` | Parse GP3/GP4/GP5 files |
| `repo_signal_analyze` | `resolve_allowed_local_file` | repo-signal analyze (read-only) |
| `repo_signal_checklist` | `resolve_allowed_local_file` | repo-signal publish checklist |
| `repo_signal_inspect` | `resolve_allowed_local_file` | repo-signal inspect --json |
| `repo_signal_doctor_json` | `resolve_allowed_local_file` | repo-signal doctor --json |
| `get_clipboard` | (none — pbpaste) | Read macOS clipboard |
| `get_wifi_info` | (none — networksetup) | Wi-Fi network name and signal |
| `get_battery_status` | (none — pmset) | Battery level and charging state |
| `list_running_apps` | (none — osascript) | Visible running macOS apps |
| `get_todays_events` | (none — osascript) | Today's Calendar events |
| `find_large_files` | (none — find) | Files over a size threshold |
| `find_recent_files` | (none — find) | Files modified within N days |
| `check_port` | (none — lsof) | Whether a TCP port is in use |
| `get_public_ip` | (none — curl api.ipify.org) | Current public IP address |

---

## Class C — Write-capable, controlled scope

Can modify files on disk within repo or explicitly allowed paths.

| Tool | Resolver | Description |
| --- | --- | --- |
| `update_repo_file` | `resolve_repo_file` | Exact-match replace in repo file |
| `edit_image` | `resolve_allowed_local_file` | Rotate or convert images |
| `set_clipboard` | (none — pbcopy) | Write text to macOS clipboard |
| `take_screenshot` | (none — screencapture) | Capture screen to a file |

`update_repo_file` has additional guards: blocked filenames (`.env`,
`uv.lock`), blocked directories (`.git`, `.venv`), allowed suffixes only,
exact-match required, refuses ambiguous matches, never commits.

---

## Class D — Subprocess and open-app

Launch external processes or open macOS applications. No file write access.

| Tool | Description |
| --- | --- |
| `open_in_app` | Open a file in its default macOS app |
| `validate_project` | Run `scripts/validate.sh` |
| `run_mqlaunch` | Open mqlaunch TUI in a new Terminal window |
| `open_repo_terminal` | Open a registered repo in a new Terminal window |
| `hal_repo_report` | Read-only mq-hal repo report |
| `open_messages` | Open Messages.app, optionally to a contact |
| `open_finder` | Open Finder at a given path |
| `open_url` | Open a URL in the default browser |
| `show_notification` | Send a macOS system notification |
| `open_app` | Launch a macOS application by name |
| `speak_text` | Speak text via macOS text-to-speech |
| `open_chrome` | Open Google Chrome, optionally to a URL |
| `open_spotify` | Open Spotify, optionally to a URI or search |
| `open_terminal` | Open a new Terminal window at a path |
| `open_vscode` | Open VS Code at a file or folder |
| `set_volume` | Set macOS system output volume |
| `toggle_dark_mode` | Toggle between dark mode and light mode |
| `lock_screen` | Lock the macOS screen immediately |
| `create_note` | Create a note in Notes.app |
| `set_reminder` | Create a reminder in Reminders.app |
| `set_wallpaper` | Set the macOS desktop wallpaper |
| `run_tests` | Run pytest in a registered local repo |

---

## Summary

| Class | Count | Write | Subprocess |
| --- | --- | --- | --- |
| A — read-only, repo-scoped | 9 | No | No |
| B — read-only, external access | 15 | No | No |
| C — write-capable, controlled | 4 | Yes | No |
| D — subprocess / open-app | 22 | No | Yes |
| **Total** | **50** | | |
