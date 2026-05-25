---
name: release-readiness
description: Use when preparing mq-mcp for release by checking versioning, changelog, tool docs, safety docs, tests, validation scripts, generated docs, and Git state.
---

# Release Readiness

Use this skill before tagging, publishing, announcing, or merging release-critical mq-mcp changes.

## Always Inspect

- `git status --short`
- `VERSION`
- `mq-mcp/pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `ROADMAP.md`
- `docs/TOOL_SAFETY.md`
- `TOOL_INDEX.md`
- `docs/integration.md`
- `scripts/validate.sh`
- `scripts/release-check.sh`
- `.github/workflows/`

## Release Risks

Block release on:

- version mismatch between `VERSION`, `mq-mcp/pyproject.toml`, README badge, and changelog
- stale tool counts or undocumented MCP tools
- failing safety or integration checks
- missing tests for path safety or write-capable tool changes
- generated docs/assets drifting unintentionally
- dirty worktree containing unrelated user changes
- secrets, `.env`, private local paths, or credentials in tracked files
- lockfile changes that were not intentional

## Verification

Run:

```bash
./scripts/release-check.sh
```

If that is too broad for the current change, use:

```bash
./scripts/validate.sh
uv --directory mq-mcp run pytest ../tests -q
python -m compileall mq-mcp/ -q
```

For tool changes, also run:

```bash
./scripts/check-mcp-tool-docs.sh
./scripts/check-integration-smoke.sh
./scripts/check-bridge-tool-discovery.sh
```

## Version Update Checklist

When bumping versions:

- update `VERSION`
- update `mq-mcp/pyproject.toml`
- update README version badge/status
- add `CHANGELOG.md` entry
- verify `scripts/release-check.sh`
- tag only after checks pass

## Report Format

Return:

- status: ready, blocked, or uncertain
- blockers
- changed files
- checks run
- checks skipped and why
- next concrete action
