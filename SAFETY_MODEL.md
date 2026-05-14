# mq-mcp Safety Model

mq-mcp is local-first and experimental.

Safety principles:
- never commit .env files
- never upload API keys or credentials
- keep filesystem access scoped to the repository root
- prefer read-only tools
- require explicit approval before write operations
- document commands that touch local files
- avoid hardcoded machine-specific paths
- validate before release

High-risk areas:
- update_repo_file can modify repository files
- run_mqlaunch may execute local workflows
- edit_image writes image output
- open_in_app opens local files in external apps
