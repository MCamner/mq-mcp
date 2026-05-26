# MCP Client Setup

This guide explains how to connect `mq-mcp` to various MCP-compatible clients on macOS.

## Prerequisites

Ensure you have installed `mq-mcp` and validated the installation:

```bash
cd mq-mcp
./scripts/install.sh
mq-mcp doctor
mq-mcp profiles validate
```

You will need the **absolute path** to your `mq-mcp` repository for the following configurations.
Profile templates live in `profiles/` and can be inspected with
`mq-mcp profiles list`.

---

## Claude Desktop

Claude Desktop is a primary client for MCP. It uses a JSON configuration file.

1.  Open the Claude Desktop configuration file:
    `~/Library/Application Support/Claude/claude_desktop_config.json`
2.  Inspect the profile template:

```bash
mq-mcp profiles show claude-desktop
```

3.  Add `mq-mcp` to the `mcpServers` section:

```json
{
  "mcpServers": {
    "mq-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/YOUR_USERNAME/path/to/mq-mcp/mq-mcp",
        "run",
        "mcp",
        "run",
        "server.py"
      ],
      "env": {
        "MQ_MCP_LOCAL_REPOS": "/Users/YOUR_USERNAME/path/to/other-repo",
        "MQ_MCP_ALLOWED_PATHS": "/Users/YOUR_USERNAME/Music:/Users/YOUR_USERNAME/Pictures"
      }
    }
  }
}
```

4.  **Replace** `YOUR_USERNAME` and the paths with your actual local paths.
5.  Restart Claude Desktop.

---

## Zed

Zed has built-in support for MCP.

1.  Open Zed and go to `Settings` (Cmd + ,).
2.  Add the following to your `settings.json`:

```json
{
  "context_servers": {
    "mq-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/YOUR_USERNAME/path/to/mq-mcp/mq-mcp",
        "run",
        "mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

3.  Restart Zed or reload the context servers.

---

## VS Code (via extensions)

Multiple VS Code extensions support MCP, such as **Roo Code (formerly Roo Cline)** or **Continue**.

### Roo Code

1.  Install the Roo Code extension.
2.  Open the Roo Code settings/configuration.
3.  Add a new MCP server with the following details:
    - **Name**: `mq-mcp`
    - **Command**: `uv`
    - **Arguments**: `--directory /Users/YOUR_USERNAME/path/to/mq-mcp/mq-mcp run mcp run server.py`

### Continue

1.  Install the Continue extension.
2.  Open `~/.continue/config.json`.
3.  Add `mq-mcp` to the `contextProviders` or `models` section if they support MCP servers directly, or follow their latest documentation for MCP integration.

---

## Troubleshooting Client Connections

- **Absolute Paths**: Always use absolute paths in configuration files.
- **Environment Variables**: If your tools depend on `MQ_MCP_LOCAL_REPOS`, ensure they are passed in the `env` block of the client configuration (as shown in the Claude Desktop example).
- **Logs**: If the server fails to start, check the client's logs. In Claude Desktop, you can often find logs in the Console app under `Claude`.
- **Validation**: Ensure `./scripts/validate.sh` passes before trying to connect a client.
