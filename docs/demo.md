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

1. get_system_resources — CPU, memory, and disk info
2. read_repo_file — reads a file inside the repository root
3. list_repo_files — lists repository files up to a chosen depth
4. search_repo — searches repository text with git grep
5. git_status — shows branch, status, and recent commits
6. git_diff — shows current git diff
7. validate_project — runs scripts/validate.sh
8. update_repo_file — safely replaces exact text in allowed repo files
9. run_mqlaunch — runs mqlaunch.sh
10. analyze_csv — analyzes CSV files
11. analyze_guitar_pro — analyzes Guitar Pro files
12. open_in_app — opens a file in its default app
13. edit_image — edits an image (resize, rotate, grayscale)
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

## Notes

This project is local-first and experimental. Review every tool before connecting it to private folders, credentials, or write-capable workflows. See [security.md](security.md) for the full safety policy.
