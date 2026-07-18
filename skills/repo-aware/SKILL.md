---
name: repo-aware
description: Use when inspecting, explaining, planning, reviewing, or changing mq-mcp with repository-specific context.
---

# Repo Aware

Use this skill to keep work grounded in mq-mcp's actual structure, safety model, and local-first MCP architecture.

## When to use

- General work on mq-mcp when no narrower skill clearly owns the task
- Understanding the repo structure, architecture, or safety model before acting
- Planning or reviewing a change that spans multiple surfaces

## When not to use

- Adding or auditing MCP tools — use `mcp-tool-safety-maintainer`
- Bridge or Bridget changes — use `bridget-bridge-maintainer`
- Release validation — use `release-readiness`
- Docs-only updates — use `docs-maintainer`
- Review engine changes — use `review-runtime-maintainer`

## Evals

### Should trigger

- "what does mq-mcp do?"
- "explain mq-mcp's architecture and safety model"
- "I'm new to mq-mcp — what are the key surfaces and patterns?"
- "what's the scope of changes I need for this mq-mcp task?"

### Should not trigger

- "update mq-mcp docs" → use `docs-maintainer`
- "add or audit an MCP tool" → use `mcp-tool-safety-maintainer`
- "fix the Bridget bridge" → use `bridget-bridge-maintainer`
- "is mq-mcp ready to release?" → use `release-readiness`

## What This Repo Is

`mq-mcp` is a local macOS MCP server and bridge toolkit. It exposes a FastMCP server, a Bridget/OpenAI bridge, macOS automation helpers, repo-analysis tools, safety documentation, GitHub Pages docs, and release validation scripts.

Primary surfaces:

- `mq-mcp/server.py` for FastMCP tools, HTTP routes, path resolvers, subprocess boundaries, and safety-critical behavior
- `mq-mcp/bridge.py` for Bridget, OpenAI tool calling, tool discovery, search modes, local image personality, and voice hooks
- `mq-mcp/ask.py` and `mq-mcp/bridget_voice.py` for local ask/voice behavior
- `scripts/validate.sh` and `scripts/release-check.sh` for validation and release readiness
- `docs/TOOL_SAFETY.md`, `SAFETY_MODEL.md`, and `docs/security.md` for tool safety policy
- `docs/integration.md`, `docs/global/`, and `VECTOR_CONTEXT.md` for the wider MQ ecosystem
- `tests/` for path safety, Bridget behavior, image behavior, and voice behavior

## First Inspection

Always start with:

```bash
git status --short
rg --files
sed -n '1,240p' README.md
sed -n '1,220p' mq-mcp/pyproject.toml
```

If changing MCP tools, inspect:

```bash
rg '^@mcp.tool|^def |resolve_|subprocess|osascript|open\\(' mq-mcp/server.py
sed -n '1,260p' docs/TOOL_SAFETY.md
sed -n '1,220p' tests/test_server_safety.py
```

If changing Bridget or bridge behavior, inspect:

```bash
sed -n '1,280p' mq-mcp/bridge.py
sed -n '1,220p' tests/test_bridget_images.py
sed -n '1,220p' tests/test_bridget_voice.py
```

## Verification

Prefer the lightest relevant check:

```bash
python -m compileall mq-mcp/ -q
uv --directory mq-mcp run pytest ../tests -q
./scripts/validate.sh
```

For tool catalog changes:

```bash
./scripts/check-mcp-tool-docs.sh
./scripts/check-bridge-tool-discovery.sh
uv --directory mq-mcp run python bridge.py --tools
```

## Guardrails

- Preserve user changes, especially local `.env`, `.claude/`, and lockfile changes.
- Default to read-only behavior unless the task explicitly needs writes or app automation.
- Keep path access scoped through `resolve_repo_file()` or `resolve_allowed_local_file()`.
- Do not add MCP tools without updating docs, tests, and validation checks.
- Keep machine-specific paths behind environment variables such as `MQ_MCP_LOCAL_REPOS` and `MQ_MCP_ALLOWED_PATHS`.
- Do not commit secrets, local credentials, screenshots with private data, or `.env` files.
