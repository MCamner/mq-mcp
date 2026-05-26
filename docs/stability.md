# Stability Baseline

`mq-mcp` v1.0.0 is the stable local MCP platform baseline for the mq ecosystem.

The stability contract is machine-readable in [`stability.json`](stability.json)
and checked by `scripts/check-stability.py`.

## Stable Commands

```bash
mq-mcp doctor
mq-mcp health
mq-mcp info --json
mq-mcp report --json
mq-mcp bundle --validate
mq-mcp profiles validate
mq-mcp validate
```

## Stable Server Startup

Local server startup is explicit:

```bash
mq-mcp serve
```

The server does not install a hidden daemon, does not autostart, and does not
silently handle credentials.

## Stable Metadata

Tool metadata is generated into:

```text
docs/tool_contracts.json
```

The schema is:

```text
tool-contracts.v1
```

Validation fails when a `@mcp.tool()` is missing from the generated contract.

## Stable Profiles

Profile templates live in:

```text
profiles/
```

They use:

```text
mq-mcp.profile.v1
```

Use `mq-mcp profiles validate` before copying profile data into clients.

## Stable Safety Model

Safety classes remain documented in:

```text
docs/TOOL_SAFETY.md
docs/TOOL_INVENTORY.md
```

File access stays bounded by:

- `resolve_repo_file`
- `resolve_allowed_local_file`
- `MQ_MCP_ALLOWED_PATHS`
- `MQ_MCP_LOCAL_REPOS`

## Release Evidence

Before a stable release:

```bash
./scripts/validate.sh
./scripts/release-check.sh
```

After release:

```bash
gh release view v1.0.0
gh api repos/MCamner/mq-mcp/branches/main/protection
```
