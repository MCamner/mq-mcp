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

## Refresh procedure

Use identity-scoped latest-only refresh through mq-agent. Do not clear the
shared canonical store to refresh one repository.

```bash
mq-agent memory status ~/mq-mcp --json
mq-agent memory refresh ~/mq-mcp --approve --cleanup-stale
mq-agent memory status ~/mq-mcp --json
```

A successful refresh requires one authoritative generation, zero
non-authoritative retrieval generations, and matching stored/current source
revisions. Underlying OpenAI Storage file objects are retained.

The historical full-pack upload scripts are guarded because they detach every
file in their target store. They are not the normal refresh path.

## Store IDs

- **semantic repository memory**: `vs_69ffa9a4ef5c81919d7d237c3ecdc260` — canonical cross-repo store and default for `ask`.
- **mq-mcp-repo-knowledge**: `vs_6a0513bc1adc8191bc18affe4383d83f` — retired consumer path. `ask` no longer reads it by default; physical historical files may remain until explicit cleanup.

## Resolver policy

`ask.py` ignores the historical `OPENAI_VECTOR_STORE_ID` setting so an old
local `.env` cannot silently reactivate the retired store. The default is the
canonical store. An intentional isolated override must use
`MQ_MCP_VECTOR_STORE_ID`.

`OPENAI_SEMANTIC_MEMORY_ID` remains an optional global-memory override. When
it resolves to the canonical ID, `ask` deduplicates it rather than sending the
same vector store twice to `file_search`.
