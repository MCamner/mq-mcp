---
name: semantic-memory-maintainer
description: Use when maintaining mq-mcp semantic memory packs, vector context, semantic index docs, global repo docs, or upload scripts.
---

# Semantic Memory Maintainer

Use this skill when mq-mcp's documentation or repo knowledge needs to stay useful for semantic retrieval and cross-repo assistant workflows.

## Relevant Files

- `VECTOR_CONTEXT.md`
- `docs/semantic-index/architecture.md`
- `docs/semantic-index/mcp-tools-map.md`
- `docs/global/GLOBAL_COMMAND_SURFACE.md`
- `docs/global/GLOBAL_ARCHITECTURE_NOTES.md`
- `docs/global/GLOBAL_REPO_MAP.md`
- `docs/global/GLOBAL_VECTOR_STORE_POLICY.md`
- `scripts/build_semantic_memory_pack.sh`
- `scripts/build_vector_pack.sh`
- `scripts/create_vector_store.py`
- `scripts/upload_semantic_memory.py`
- `scripts/upload_vector_pack.py`
- `scripts/vignette.py`

## Maintenance Rules

- Keep semantic docs factual and compact.
- Prefer stable architecture, command, safety, and integration facts over changelog noise.
- Do not include secrets, local credentials, private tokens, or broad personal filesystem details.
- Keep tool maps synchronized with `mq-mcp/server.py` and `docs/TOOL_SAFETY.md`.
- Keep global docs clear about what is repo-specific versus ecosystem-wide.
- Treat upload scripts as opt-in operations that require explicit user intent.

## When Tool Surface Changes

Update:

- `docs/semantic-index/mcp-tools-map.md`
- `VECTOR_CONTEXT.md` if retrieval context should know the new capability
- `docs/global/GLOBAL_COMMAND_SURFACE.md` if the command affects the wider MQ ecosystem
- safety docs if the change touches risk or access scope

## Verification

```bash
./scripts/check-mcp-tool-docs.sh
./scripts/check-integration-docs.sh
./scripts/build_semantic_memory_pack.sh
```

Only run upload commands when requested:

```bash
python scripts/upload_semantic_memory.py
python scripts/upload_vector_pack.py
```

## Review Standard

A good semantic update should improve retrieval precision. Remove stale or misleading claims instead of adding more text around them.
