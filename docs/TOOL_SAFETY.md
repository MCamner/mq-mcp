# MCP Tool Safety Classification

This document classifies all 13 tools exposed by `mq-mcp/server.py` by what they are
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
| `analyze_csv` | Read and summarize a CSV inside repo | Write, access outside repo |
| `tool_safety_report` | Return contents of docs/TOOL_SAFETY.md | Write, access outside repo |
| `repo_signal_analyze` | Run repo-signal analyze on an allowed repo path | Write, access outside allowed roots |
| `repo_signal_checklist` | Run repo-signal publish checklist on an allowed repo path | Write, access outside allowed roots |

Resolver: `resolve_repo_file` (git_status and git_diff use `run_repo_command` with `cwd=REPO_ROOT`)

---

## Class B — Read-only, allowed external paths

These tools cannot write files and cannot run processes. They can read files outside the repo if `MQ_MCP_ALLOWED_PATHS` is configured.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `get_system_resources` | Read CPU, memory, disk stats via psutil | Write, access files |
| `analyze_guitar_pro` | Parse GP3/GP4/GP5 files in repo or allowed roots | Write, access outside allowed roots |

Resolver: `resolve_allowed_local_file` (analyze_guitar_pro), none (get_system_resources)

---

## Class C — Write-capable, controlled scope

These tools can modify files on disk. They are scoped to the repo or explicitly allowed paths.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `update_repo_file` | Replace exact text in allowed repo files | Write outside repo, commit, auto-delete, binary files |
| `edit_image` | Rotate or convert images in repo or allowed roots | Write outside allowed roots, commit, delete |

`update_repo_file` has additional guards: blocked filenames (`.env`, `uv.lock`), blocked directories (`.git`, `.venv`), allowed suffixes only, exact-match required, refuses ambiguous matches, never commits.

Resolver: `resolve_repo_file` (update_repo_file), `resolve_allowed_local_file` (edit_image)

---

## Class D — Subprocess / open-app

These tools invoke external processes or open applications. Review carefully before extending.

| Tool | What it can do | What it cannot do |
| --- | --- | --- |
| `open_in_app` | Open a file in its default macOS app | Accepts only repo or allowed-root paths |
| `validate_project` | Run `scripts/validate.sh` with a 60s timeout | Run arbitrary commands |
| `run_mqlaunch` | Open `mqlaunch.sh` in a new Terminal window via osascript | — |

Resolver: `resolve_allowed_local_file` (open_in_app), fixed script path (validate_project, run_mqlaunch)

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
| `repo_signal_analyze` | B | resolve_allowed_local_file | No | No |
| `repo_signal_checklist` | B | resolve_allowed_local_file | No | No |
| `get_system_resources` | B | psutil (no file path) | No | No |
| `analyze_guitar_pro` | B | resolve_allowed_local_file | No | No |
| `tool_safety_report` | A | resolve_repo_file (implicit) | No | No |
| `update_repo_file` | C | resolve_repo_file | Yes | No |
| `edit_image` | C | resolve_allowed_local_file | Yes | No |
| `open_in_app` | D | resolve_allowed_local_file | No | Yes |
| `validate_project` | D | fixed path | No | Yes |
| `run_mqlaunch` | D | fixed path | Potentially | Yes |
