# mq-mcp Demo

Small local examples of mq-mcp in action. Run all commands from the repository root.

## List available tools

```bash
uv --directory mq-mcp run python bridge.py "List the available MCP tools."
```

Expected output (abbreviated):

```
--- mq-mcp bridge: Model Context Protocol <-> OpenAI ---
Model: gpt-4.1
Prompt: List the available MCP tools.

Bridget: Here are the available MCP tools:

1.  tool_safety_report — returns the MCP tool safety classification
2.  get_system_resources — CPU, memory, and disk info
3.  read_repo_file — reads a file inside the repository root
4.  list_repo_files — lists repository files up to a chosen depth
5.  search_repo — searches repository text with git grep
6.  git_status — shows branch, status, and recent commits
7.  git_diff — shows current git diff
8.  validate_project — runs scripts/validate.sh
9.  update_repo_file — safely replaces exact text in allowed repo files
10. run_mqlaunch — runs mqlaunch.sh
11. analyze_csv — analyzes CSV files
12. analyze_guitar_pro — analyzes Guitar Pro files
13. open_in_app — opens a file in its default app
14. edit_image — edits an image (resize, rotate, grayscale)
```

## Check system resources

```bash
uv --directory mq-mcp run python bridge.py "Check local system resources."
```

## Read repository context

```bash
uv --directory mq-mcp run python bridge.py "Read README.md and summarize the project."
```

## Check git state

```bash
uv --directory mq-mcp run python bridge.py "Show git status and recent commits."
```

## Run validation

```bash
uv --directory mq-mcp run python bridge.py "Run project validation."
```

Or directly:

```bash
./scripts/validate.sh
```

Expected output:

```
[OK] server.py
[OK] bridge.py
[OK] main.py
[OK] pyproject.toml
[OK] .env.example
[OK] MCP tool listing works
[OK] read_repo_file tool present
[OK] list_repo_files tool present
[OK] search_repo tool present
[OK] git_status tool present
[OK] git_diff tool present
[OK] validate_project tool present
[OK] update_repo_file tool present
All checks passed.
```

## Bridget safety map demo

Use Bridget to inspect the MCP tool safety classification through the read-only `tool_safety_report` tool.

### Ask for the safety map

```bash
uv --directory mq-mcp run python bridge.py "Use tool_safety_report and summarize the MCP tool safety map."
```

Expected behavior:

- Bridget reads `docs/TOOL_SAFETY.md` through `tool_safety_report`.
- The response summarizes tool scope, access type, and risk level.
- No files are modified. No external paths are accessed.

### Targeted safety questions

```bash
uv --directory mq-mcp run python bridge.py "Which MCP tools are read-only?"
uv --directory mq-mcp run python bridge.py "Which MCP tools can write files?"
uv --directory mq-mcp run python bridge.py "Which MCP tools run subprocesses?"
uv --directory mq-mcp run python bridge.py "Which MCP tools can access explicitly allowed local paths?"
```

Expected behavior:

- Read-only tools (Class A/B) are identified separately from write-capable tools (Class C).
- Subprocess tools (Class D) are called out clearly.
- Tools using `MQ_MCP_ALLOWED_PATHS` are identified as allowlist-scoped.

### Safety rule

`tool_safety_report` is intentionally read-only. It only returns the repository safety documentation. It does not run commands, modify files, or access external paths.

## Notes

This project is local-first and experimental. Review every tool before connecting it to private folders, credentials, or write-capable workflows. See [security.md](security.md) for the full safety policy.
