# MCP Server Profiles

Server profiles allow you to configure `mq-mcp` for specific use cases by adjusting environment variables and client settings.

## Profile: Standard (Safe / Minimal)

Best for: Reviewing the `mq-mcp` repository itself with maximum safety.

**Environment (`.env`):**
```bash
# No extra repos or paths
MQ_MCP_LOCAL_REPOS=""
MQ_MCP_ALLOWED_PATHS=""
```

**Key Tools:** `read_repo_file`, `list_repo_files`, `git_status`, `validate_project`.

---

## Profile: Full Developer (Multi-Repo)

Best for: Working across multiple projects and using Bridget as a central assistant.

**Environment (`.env`):**
```bash
# Register all your active projects
MQ_MCP_LOCAL_REPOS="/Users/name/repo-signal,/Users/name/mq-hal,/Users/name/my-app"
# No external path access needed
MQ_MCP_ALLOWED_PATHS=""
```

**Key Tools:** `hal_repo_report`, `repo_signal_analyze`, `list_local_repos`, `open_repo_terminal`.

---

## Profile: Media & Creative

Best for: Managing music files (Guitar Pro) and performing quick image edits.

**Environment (`.env`):**
```bash
# Allow access to your creative folders
MQ_MCP_ALLOWED_PATHS="/Users/name/Music/Tabs:/Users/name/Pictures/Assets"
```

**Key Tools:** `analyze_guitar_pro`, `edit_image`, `open_in_app`.

---

## Profile: System Monitor

Best for: Keeping an eye on local system health while working.

**Environment (`.env`):**
```bash
# Standard config
```

**Key Tools:** `get_system_resources`.

---

## Implementing Profiles in Clients

You can define these profiles directly in your `claude_desktop_config.json` by creating multiple server entries with different names and environments.

### Example: Claude Desktop with Profiles

```json
{
  "mcpServers": {
    "mq-mcp-safe": {
      "command": "uv",
      "args": ["--directory", "/path/to/mq-mcp/mq-mcp", "run", "mcp", "run", "server.py"],
      "env": {
        "MQ_MCP_LOCAL_REPOS": ""
      }
    },
    "mq-mcp-dev": {
      "command": "uv",
      "args": ["--directory", "/path/to/mq-mcp/mq-mcp", "run", "mcp", "run", "server.py"],
      "env": {
        "MQ_MCP_LOCAL_REPOS": "/path/to/repo1,/path/to/repo2"
      }
    }
  }
}
```

By doing this, you can choose which "profile" of the server to talk to depending on your current task.
