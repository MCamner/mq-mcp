# Installation guide

This guide explains how to install and validate `mq-mcp` locally on macOS.

## Requirements

- macOS
- Git
- Python 3.14 or later (managed automatically by `uv`)
- [uv](https://docs.astral.sh/uv/)
- OpenAI API key (only needed for bridge prompts that call OpenAI)

## Clone

```bash
git clone https://github.com/MCamner/mq-mcp.git
cd mq-mcp/mq-mcp
```

## Install dependencies

```bash
uv sync
```

## List MCP tools

```bash
uv run python bridge.py --tools
```

## Run the MCP server

```bash
uv run mcp run server.py
```

## Run the bridge

```bash
uv run python bridge.py "List the available MCP tools."
```

## Validate the project

From the repository root:

```bash
cd ..
./scripts/validate.sh
```

## Environment

Copy the example environment file before using bridge prompts that need an API key:

```bash
cp .env.example .env
```

Edit `.env` and add your `OPENAI_API_KEY`. Do not commit this file.

## Notes

This is a local-first experimental MCP project. Review exposed tools before extending file access or write capabilities.
