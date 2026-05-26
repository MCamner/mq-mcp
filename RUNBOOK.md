# mq-mcp Runbook

## Install

```bash
cd mq-mcp
uv sync
```

## Run entry point

```bash
uv run python main.py
```

## Run MCP server

```bash
uv run mcp run server.py
```

## Run bridge

```bash
uv run python bridge.py "List the available MCP tools."
```

## Validate from repo root

```bash
./scripts/validate.sh
```

## Run tests

```bash
uv --directory mq-mcp run pytest ../tests -v
```

## Release check

Review:

- git status
- VERSION
- CHANGELOG.md
- README.md
- validation result
- tests
- docs
- secrets
