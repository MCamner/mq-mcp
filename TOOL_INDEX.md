# mq-mcp Tool Index

The local MCP server exposes tools for local system information, repository inspection, validation, file analysis, and controlled file updates.

Core tools:

* get_system_resources: CPU, memory, and disk info
* read_repo_file: reads a file inside the repository root
* list_repo_files: lists repository files up to a chosen depth
* search_repo: searches repository text with git grep
* git_status: shows branch, status, and recent commits
* git_diff: shows current git diff
* validate_project: runs scripts/validate.sh
* update_repo_file: safely replaces exact text in allowed repo files, no auto-commit
* run_mqlaunch: runs mqlaunch.sh
* analyze_csv: analyzes CSV files
* analyze_guitar_pro: analyzes Guitar Pro files
* open_in_app: opens a file in its default app
* edit_image: edits an image (resize, rotate, grayscale)

Review engine tools:

* list_review_contracts: lists available review contracts and their modes
* review_file: runs an AI review on a repo file using a review contract (requires OPENAI_API_KEY)
* build_repo_context: rebuilds architecture_map.json and file_summary_index.json for the review engine
* list_review_history: lists all files with review history and last review summary
* get_last_review: returns the most recent review findings for a repo file from local memory
* detect_architecture_drift: detects drift between declared documentation and actual runtime state
* review_diff: reviews all git-changed files using the configured review mode (requires OPENAI_API_KEY)
* review_repo: reviews the least-recently-reviewed repo files (requires OPENAI_API_KEY)
* review_runtime_contract: verifies RUNTIME_CONTRACT.md claims against actual server state; structural checks + AI architecture pass
* validate_orchestration_contract: verifies tool set satisfies the orchestration contract; checks profiles, safety classes, error prefixes (Class A)
* list_architecture_docs: lists docs/architecture/ with freshness status relative to server.py
* review_architecture_doc: applies architecture review contract to a named architecture document with injected runtime state
* list_architecture_decisions: lists all architecture memory entries (ADRs, boundaries, philosophy, rejected patterns)
* get_architecture_decision: returns the full text of a specific architecture memory entry by ID
* record_architecture_decision: records a new architecture decision in architecture_memory/ (Class C)
* extract_coding_conventions: extracts generalizable coding conventions from the last review of a file and persists them to architecture_memory/ (Class C, requires OPENAI_API_KEY)
* store_semantic_memory: stores or updates a knowledge item in semantic_memory/store.json (Class C)
* search_semantic_memory: keyword search across semantic memory keys, tags, and content (Class A)
* get_semantic_memory: returns full content of a semantic memory item by key (Class A)
* list_semantic_memory: lists all semantic memory items with key, tags, preview (Class A)
* bootstrap_semantic_memory: ingests README, ROADMAP, and key contract docs into semantic memory (Class C)
* export_symbol_index: writes the callgraph symbol map to generated/symbols/symbol_index.json (Class C)
* repo_signal_status: reports whether repo-signal export packs are present, their age, and merge status (Class A)
* risk_review_file: targeted risk pass (security/risk/architecture mode) with grep pre-scan + AI review (Class A)
* risk_review_diff: risk pass over all changed files in working tree or staging area (Class A)

Important safety distinction:
Read-only tools should be preferred by default. Write-capable tools such as update_repo_file and edit_image require extra care and explicit user approval.
