# MCP safety policy

## Tool safety matrix

| Tool | Access | Write | Notes |
| --- | --- | --- | --- |
| `get_system_resources` | Local system | No | CPU, memory, disk |
| `read_repo_file` | Repo root | No | Scoped to repo |
| `list_repo_files` | Repo root | No | Scoped to repo |
| `search_repo` | Repo root | No | git grep, read-only |
| `git_status` | Git metadata | No | Read-only |
| `git_diff` | Git metadata | No | Read-only |
| `validate_project` | Local command | No | Runs validate.sh |
| `update_repo_file` | Repo root | Yes | Exact replacement only, no auto-commit |
| `analyze_csv` | Repo root | No | CSV analysis |
| `analyze_guitar_pro` | Repo + `MQ_MCP_ALLOWED_PATHS` | No | Guitar Pro analysis |
| `open_in_app` | Repo + `MQ_MCP_ALLOWED_PATHS` | No | Opens file externally |
| `edit_image` | Repo + `MQ_MCP_ALLOWED_PATHS` | Yes | Writes edited output |
| `run_mqlaunch` | Local command | Potentially | Review before use |

`mq-mcp` is local-first and experimental. The MCP server exposes tools that can inspect the repository and, in limited cases, update files.

## Tool categories

### Read-only tools — repo-scoped

These tools do not modify files and are restricted to the repository root:

- `read_repo_file`
- `list_repo_files`
- `search_repo`
- `git_status`
- `git_diff`

### Read-only tools — system or allowed paths

These tools do not modify files, but may inspect system state or read files outside the repo:

- `get_system_resources`
- `analyze_csv`
- `analyze_guitar_pro` — repo root + paths listed in `MQ_MCP_ALLOWED_PATHS`

### Controlled action tools — repo-scoped

These tools can perform controlled local actions inside the repository root:

- `validate_project`
- `update_repo_file`

### Controlled action tools — allowed paths

These tools can affect local files or applications. External file access is gated by `MQ_MCP_ALLOWED_PATHS`:

- `run_mqlaunch` — opens a Terminal window
- `open_in_app` — repo root + `MQ_MCP_ALLOWED_PATHS`
- `edit_image` — repo root + `MQ_MCP_ALLOWED_PATHS`

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

## External path policy

`analyze_guitar_pro`, `open_in_app`, and `edit_image` use `resolve_allowed_local_file()` instead of the stricter repo-only resolver. This allows absolute paths or paths under explicitly configured directories:

```bash
# mq-mcp/.env
MQ_MCP_ALLOWED_PATHS="/Users/mansys/Music:/Users/mansys/Pictures"
```

- Paths are colon-separated absolute directories.
- Unset or empty `MQ_MCP_ALLOWED_PATHS` means these tools are restricted to the repo root.
- Path traversal outside all allowed roots raises `ValueError`.
- See `.env.example` for the full template.

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

## Branch protection recommendation

Protect the `main` branch to prevent force-pushes and unreviewed merges.

Recommended settings on GitHub → Settings → Branches → Add rule for `main`:

- Require a pull request before merging
- Require status checks to pass before merging:
  - `Validate` (`.github/workflows/validate.yml`)
  - `Docs consistency` (`.github/workflows/docs-consistency.yml`)
- Do not allow bypassing the above settings
- Do not allow force pushes
- Do not allow deletions

This ensures every merge to `main` has passed CI before landing.

## GitHub Actions release checklist

Before tagging a release, confirm the following in GitHub Actions:

1. Open the repository on GitHub and click **Actions**.
2. Confirm the latest commit on `main` shows green checks for:
   - `Validate` workflow — MCP tool listing, required files,
     Python compile, integration wiring
   - `Docs consistency` workflow — version sync, stale tool counts,
     Python version accuracy
3. If any workflow is red, read the failed step output and fix
   locally before pushing.
4. Run `./scripts/release-check.sh` locally and confirm
   `release-check passed — ready for vX.Y.Z`.
5. Create the GitHub release:
   - Tag: `vX.Y.Z`
   - Title: `vX.Y.Z — <milestone name>`
   - Body: paste the relevant CHANGELOG section
6. Confirm GitHub Pages deploys successfully after the release.
