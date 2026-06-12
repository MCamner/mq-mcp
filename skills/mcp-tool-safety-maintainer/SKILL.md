---
name: mcp-tool-safety-maintainer
description: Use when adding, changing, reviewing, or documenting mq-mcp FastMCP tools, path resolvers, write-capable tools, subprocess tools, or safety classifications.
---

# MCP Tool Safety Maintainer

Use this skill for the highest-risk part of mq-mcp: the tool surface exposed by `mq-mcp/server.py`.

## When to use

* Adding, changing, reviewing, or documenting any FastMCP tool in `server.py`
* Auditing path resolvers, write-capable tools, subprocess behavior, or tool safety classifications
* Updating `docs/TOOL_SAFETY.md`, `TOOL_INDEX.md`, or safety tests after tool changes

## When not to use

* Bridge or Bridget changes — use `bridget-bridge-maintainer`
* Review engine changes — use `review-runtime-maintainer`
* Docs-only updates not touching tool safety — use `docs-maintainer`
* Semantic memory changes — use `semantic-memory-maintainer`

## Evals

### Should trigger

* "add a new MCP tool that reads battery status"
* "audit the path resolvers for traversal escapes"
* "should this new tool be Class B or Class C?"
* "update TOOL_SAFETY.md after the tool change"

### Should not trigger

* "Bridget tool discovery is broken" → use `bridget-bridge-maintainer`
* "add a review contract" → use `review-runtime-maintainer`
* "the README is stale but no tool changed" → use `docs-maintainer`
* "rebuild semantic memory" → use `semantic-memory-maintainer`

## Safety Model

mq-mcp tools are grouped into:

* Class A: read-only, repo-scoped
* Class B: read-only, allowed external paths or system state
* Class C: write-capable, controlled scope
* Class D: subprocess or open-app actions

Keep this classification current in `docs/TOOL_SAFETY.md`.

## Files To Inspect

* `mq-mcp/server.py`
* `docs/TOOL_SAFETY.md`
* `SAFETY_MODEL.md`
* `docs/security.md`
* `TOOL_INDEX.md`
* `README.md`
* `docs/semantic-index/mcp-tools-map.md`
* `scripts/check-mcp-tool-docs.sh`
* `scripts/check-integration-smoke.sh`
* `tests/test_server_safety.py`
* `tests/test_allowed_local_paths.py`

## Resolver Rules

Use `resolve_repo_file()` for repo-only file access.

Use `resolve_allowed_local_file()` for repo files plus explicitly allowed external roots from `MQ_MCP_ALLOWED_PATHS` or registered repos from `MQ_MCP_LOCAL_REPOS`.

Never accept arbitrary paths for write-capable tools. Avoid raw absolute paths unless the tool has an explicit, documented reason and test coverage.

## Adding Or Changing A Tool

For every MCP tool change:

1. Confirm whether the tool reads, writes, opens apps, launches subprocesses, or accesses network.
2. Choose the narrowest resolver or allowlist.
3. Set timeouts on subprocess calls.
4. Return concise error strings without leaking secrets.
5. Add or update tests for path traversal, blocked files, missing files, and output shape.
6. Update `docs/TOOL_SAFETY.md`, `TOOL_INDEX.md`, README tool lists, and semantic index docs.
7. Update validation scripts if the tool is part of the expected public catalog.

## Special Care

Watch these tools closely:

* `update_repo_file`: exact-match only, no `.env`, no lockfiles, no hidden/system dirs, no auto-commit
* `edit_image`: overwrites files, must stay scoped to allowed roots
* `take_screenshot`: writes local screenshots and may capture sensitive data
* `open_*` tools: app-launch and URL/path validation matters
* `run_tests`: executes code in registered repos only
* `repo_signal_*` and `hal_repo_report`: must remain read-only integrations

## Verification

```bash
python -m compileall mq-mcp/server.py -q
uv --directory mq-mcp run pytest ../tests/test_server_safety.py ../tests/test_allowed_local_paths.py -q
./scripts/check-mcp-tool-docs.sh
./scripts/check-integration-smoke.sh
uv --directory mq-mcp run python bridge.py --tools
```

## Review Standard

Lead with safety regressions, path escapes, undocumented tool behavior, stale tool counts, missing tests, and subprocess risks. Treat documentation drift as a bug because the tool surface is user-facing.
