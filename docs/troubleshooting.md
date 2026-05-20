# Troubleshooting

Common issues and solutions for `mq-mcp` on macOS.

## Tooling

### `uv` not found

If `uv` is not found, install it via the official script:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal after installation.

### Python version mismatch

`mq-mcp` requires Python 3.11 or later. `uv` handles this automatically if you run commands through it. If you need to install a specific version:

```bash
uv python install 3.12
```

## Credentials

### Missing `OPENAI_API_KEY`

If the bridge fails with a missing API key error:

1.  Ensure you are in the `mq-mcp/mq-mcp/` directory.
2.  Check if `.env` exists. If not, copy it: `cp .env.example .env`.
3.  Add your key: `OPENAI_API_KEY=sk-...` inside `.env`.
4.  Ensure you are NOT committing this file.

## MCP Server

### Server fails to start

If `uv run mcp run server.py` fails:

1.  **Dependencies**: Run `uv sync` to ensure all packages are installed.
2.  **Syntax**: Run `python -m compileall server.py` to check for syntax errors.
3.  **Port conflict**: If the server uses a specific port, ensure it's not occupied. FastMCP typically uses standard I/O for local MCP, so this is rarely an issue unless using a remote transport.
4.  **Permissions**: Ensure `server.py` and the `mq-mcp` folder are readable by your user.

### Tools not visible

If `uv run python bridge.py --tools` shows an empty list or missing tools:

1.  Check `server.py` for errors.
2.  Ensure the `@mcp.tool()` decorators are correctly applied.
3.  Run the validation script: `./scripts/validate.sh` from the repo root.

## Integration

### `mq-hal` or `repo-signal` not found

The integration tools require these projects to be installed locally and registered in your environment:

1.  Install `mq-hal` and `repo-signal` in their respective directories.
2.  Add them to `MQ_MCP_LOCAL_REPOS` in your `.env`:
    ```bash
    MQ_MCP_LOCAL_REPOS="/Users/yourname/mq-hal,/Users/yourname/repo-signal"
    ```
3.  Restart the MCP server or bridge.

## Still having issues?

1.  Run the full validation: `./scripts/validate.sh`.
2.  Check the [Safety notes](security.md) to ensure your paths are allowed.
3.  Open an issue on GitHub with the output of the failing command.
