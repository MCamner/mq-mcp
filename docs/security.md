# MCP safety policy

`mq-mcp` is local-first and experimental. The MCP server exposes tools that can inspect the repository and, in limited cases, update files.

## Tool categories

### Read-only tools — repo-scoped

These tools do not modify files and are restricted to the repository root:

- `read_repo_file`
- `list_repo_files`
- `search_repo`
- `git_status`
- `git_diff`

### Read-only tools — system or broad access

These tools do not modify files, but may inspect system state or read user-provided files:

- `get_system_resources`
- `analyze_csv`
- `analyze_guitar_pro`

### Controlled action tools — repo-scoped

These tools can perform controlled local actions inside the repository root:

- `validate_project`
- `update_repo_file`

### Controlled action tools — broad access

These tools can affect local files or applications and should be reviewed carefully before expansion:

- `run_mqlaunch`
- `open_in_app`
- `edit_image`

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

Run the safety tests from the repository root:

```bash
uv --directory mq-mcp run pytest ../tests -v
```

## Safe workflow

1. Inspect
2. Propose
3. Update exact text
4. Show diff
5. Human reviews
6. Human commits
