# MCP safety policy

`mq-mcp` is local-first and experimental. The MCP server exposes tools that can inspect the repository and, in limited cases, update files.

## Tool categories

### Read-only tools

These tools do not modify files:

- `get_system_resources`
- `read_repo_file`
- `list_repo_files`
- `search_repo`
- `git_status`
- `git_diff`
- `analyze_csv`
- `analyze_guitar_pro`

### Controlled action tools

These tools can perform local actions:

- `validate_project` — runs the local validation script
- `run_mqlaunch` — runs `mqlaunch.sh`
- `open_in_app` — opens a file in its default application
- `edit_image` — applies in-place image transforms
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
