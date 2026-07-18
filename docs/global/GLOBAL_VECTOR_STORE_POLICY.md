# Global Vector Store Policy

## What goes in

| Category | Include |
|---|---|
| Project docs | README.md, CHANGELOG.md, ROADMAP.md, VERSION, LICENSE |
| AI context | VECTOR_CONTEXT.md, TOOL_INDEX.md, SAFETY_MODEL.md, RUNBOOK.md |
| Semantic index | docs/semantic-index/*.md, docs/global/GLOBAL_*.md |
| Key source | cli.py, server.py, bridge.py, ask.py, publish_checklist.py |
| Shell commands | mqlaunch.sh, *.sh in launchers/, menus/, tools/ |
| Wiki / docs | docs/**/*.md, docs/**/*.html |
| CI | .github/workflows/*.yml |
| Tests | test_cli.py, test_semantic_upload.py (selected, not all) |
| Skills | skills/**/SKILL.md |

## What stays out — always

| Category | Exclude |
|---|---|
| Secrets | .env, .env.*,*.key, *.pem,*.p12, *.mobileconfig |
| Large assets | *.png,*.jpg, *.gif,*.mp4, *.zip,*.tar.gz, *.dmg |
| Caches | .git/, .venv/, **pycache**/, node_modules/, .pytest_cache/ |
| Lock files | uv.lock, package-lock.json, pnpm-lock.yaml, yarn.lock |
| Backups | backups/, *.bak |
| Logs | *.log |
| System | .DS_Store |

## File naming in the pack

Files are flattened to a single directory using:

```text
{repo-name}__{relative__path__with__double__underscores}.ext
```

Example: `mq-mcp/mq-mcp/server.py` → `mq-mcp__mq-mcp__server.py`

`.toml` files are renamed to `.toml.txt` (OpenAI vector store does not index `.toml`).

## Rebuild procedure

```bash
# 1. Build pack
bash ~/mq-mcp/scripts/build_semantic_memory_pack.sh

# 2. Upload (replaces all files in the store)
cd ~/mq-mcp/mq-mcp && uv run python ../scripts/upload_semantic_memory.py
```

## Store IDs

- **semantic repository memory**: `vs_69ffa9a4ef5c81919d7d237c3ecdc260` — global cross-repo master
- **mq-mcp-repo-knowledge**: `vs_6a0513bc1adc8191bc18affe4383d83f` — mq-mcp only, used by `ask` CLI
