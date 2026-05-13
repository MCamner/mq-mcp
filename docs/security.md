# MCP safety policy

`mq-mcp` is local-first and experimental. The MCP server exposes tools that can inspect the repository and, in limited cases, update files.

## Tool categories

### Read-only tools (repo-scoped)

These tools do not modify files and are restricted to the repository root:

- `get_system_resources`
- `read_repo_file`
- `list_repo_files`
- `search_repo`
- `git_status`
- `git_diff`
- `analyze_csv`

### Read-only tools (broad access)

These tools do not modify files but may access paths outside the repository root by design:

- `analyze_guitar_pro` — reads Guitar Pro files from the Guitar Pro 8 application

### Controlled action tools (broad access)

These tools can perform local actions and may access paths outside the repository root by design:

- `open_in_app` — opens a file in its default application (e.g. Photoshop)
- `edit_image` — applies in-place image transforms; may access files in external application folders

### Controlled action tools (repo-scoped)

These tools can modify files but are restricted to the repository root:

- `validate_project` — runs the local validation script
- `run_mqlaunch` — runs `mqlaunch.sh`
- `update_repo_file` — replaces exact text in allowed repo files

## File update policy

`update_repo_file` is intentionally limited:

- only writes inside the repository root
- only updates allowed text-like files (`.md`, `.txt`, `.py`, `.sh`, `.toml`, `.yaml`, `.yml`, `.json`, `.html`, `.css`, `.js`)
- blocks `.env`, `.env.local`, `.envrc`, `uv.lock`
- blocks paths inside `.git`, `.venv`, `__pycache__`, `node_modules`
- requires non-empty `old_text`
- refuses if no exact match is found
- refuses if the match appears more than once
- never commits changes automatically

## Git policy

The bridge may inspect Git state and show diffs. It should not:

- run arbitrary shell commands
- commit automatically
- push automatically
- delete files without explicit human review

## Validation

Run the local validation script:

```bash
./scripts/validate.sh
```

Run the safety tests:

```bash
uv --directory mq-mcp run pytest tests/ -v
```

## Design principle

Prefer small, reviewable, reversible changes.

The safe workflow is:

1. inspect
2. propose
3. update exact text
4. show diff
5. human reviews
6. human commits
