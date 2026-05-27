# mq-mcp Tool Index

The local MCP server exposes tools for local system information, repository inspection, validation, file analysis, and controlled file updates.

Core tools:

- get_system_resources: CPU, memory, and disk info
- read_repo_file: reads a file inside the repository root
- list_repo_files: lists repository files up to a chosen depth
- search_repo: searches repository text with git grep
- git_status: shows branch, status, and recent commits
- git_diff: shows current git diff
- validate_project: runs scripts/validate.sh
- update_repo_file: safely replaces exact text in allowed repo files, no auto-commit
- run_mqlaunch: runs mqlaunch.sh
- analyze_csv: analyzes CSV files
- analyze_guitar_pro: analyzes Guitar Pro files
- open_in_app: opens a file in its default app
- edit_image: edits an image (resize, rotate, grayscale)

Review engine tools:

- list_review_contracts: lists available review contracts and their modes
- review_file: runs an AI review on a repo file using a review contract (requires OPENAI_API_KEY)
- build_repo_context: rebuilds architecture_map.json and file_summary_index.json for the review engine

Important safety distinction:
Read-only tools should be preferred by default. Write-capable tools such as update_repo_file and edit_image require extra care and explicit user approval.
