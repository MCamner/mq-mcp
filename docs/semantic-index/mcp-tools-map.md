# MCP Tools Map

All tools exposed by `mq-mcp/server.py` via FastMCP.

## Tool catalog

| Tool | File | Function | Scope | Risk | Notes |
| --- | --- | --- | --- | --- | --- |
| `get_system_resources` | server.py | `get_system_resources` | system | read-only | CPU, memory, disk via psutil |
| `read_repo_file` | server.py | `read_repo_file` | repo files | read-only | Path-sandboxed to REPO\_ROOT |
| `list_repo_files` | server.py | `list_repo_files` | repo tree | read-only | Excludes .git, .venv, \_\_pycache\_\_ |
| `search_repo` | server.py | `search_repo` | repo text | read-only | Uses `git grep -n` |
| `git_status` | server.py | `git_status` | git | read-only | Branch, status, last 5 commits |
| `git_diff` | server.py | `git_diff` | git | read-only | Full diff or per-file diff |
| `update_repo_file` | server.py | `update_repo_file` | repo files | write | Exact-match replace, no auto-commit. Allowed suffixes: .md .txt .py .sh .toml .yaml .yml .json .html .css .js |
| `validate_project` | server.py | `validate_project` | scripts | execution | Runs `scripts/validate.sh` (bash, timeout 60s) |
| `run_mqlaunch` | server.py | `run_mqlaunch` | shell | execution | Opens mqlaunch.sh in a new Terminal window via osascript |
| `analyze_csv` | server.py | `analyze_csv` | repo files | read-only | Reads CSV with pandas |
| `analyze_guitar_pro` | server.py | `analyze_guitar_pro` | repo + MQ\_MCP\_ALLOWED\_PATHS | read-only | Parses GP3/GP4/GP5 files |
| `open_in_app` | server.py | `open_in_app` | repo + MQ\_MCP\_ALLOWED\_PATHS | execution | Opens file with macOS `open` command |
| `edit_image` | server.py | `edit_image` | repo + MQ\_MCP\_ALLOWED\_PATHS | write | rotate, grayscale — overwrites in place |

## Safety tiers

| Tier | Tools |
| --- | --- |
| Safe (read-only) | get\_system\_resources, read\_repo\_file, list\_repo\_files, search\_repo, git\_status, git\_diff, analyze\_csv, analyze\_guitar\_pro |
| Write | update\_repo\_file, edit\_image |
| Execution | validate\_project, run\_mqlaunch, open\_in\_app |

## Path security

`read_repo_file`, `update_repo_file`, `git_diff`, and `analyze_csv` resolve paths through
`resolve_repo_file()` which calls `.relative_to(REPO_ROOT.resolve())` and raises `ValueError`
on path traversal attempts.

`analyze_guitar_pro`, `open_in_app`, and `edit_image` use `resolve_allowed_local_file()` —
accepts repo-relative or absolute paths within `MQ_MCP_ALLOWED_PATHS`; raises `ValueError`
on traversal outside all allowed roots.

## Key constants

- `REPO_ROOT = Path(__file__).resolve().parent.parent` — points to `~/mq-mcp`
- `run_repo_command()` — all git/bash commands run with `cwd=REPO_ROOT`, `timeout=20`
