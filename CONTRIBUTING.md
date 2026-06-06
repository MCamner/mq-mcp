# Contributing to mq-mcp

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management

## Setup

```bash
git clone https://github.com/MCamner/mq-mcp.git
cd mq-mcp
uv --directory mq-mcp sync
```

## Running tests

The test suite lives in `tests/` but depends on the `mq-mcp/` project environment:

```bash
uv --directory mq-mcp run pytest ../tests/ -q
```

## Full validation

```bash
bash scripts/validate.sh
```

This runs contract checks, Bridget identity checks, and tool surface validation.
CI also runs the test suite as a separate step after `validate.sh`.

## Conventions

- All MCP tools must have a contract entry in `docs/tool_contracts.json`.
- Safety class (`read`, `write`, `subprocess`) must be declared per tool — see `SAFETY_MODEL.md`.
- New learn engine entries go through `record_learning`; manual edits to `learn_engine/memory/lessons.jsonl` must include non-empty `problem`, `lesson`, and `solution` fields.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`.

## Pull requests

Open a PR against `main`. CI runs `scripts/validate.sh` automatically. Keep PRs focused — one concern per PR.
