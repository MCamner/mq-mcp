---
name: brain-maintainer
description: Use when changing the mqobsidian second brain, `brain_*` MCP tools, the Obsidian writer, vault schemas, or the knowledge contract.
---

# Brain Maintainer

Use this skill for mq-mcp's Obsidian second-brain surface: the vault writer, the `brain_*` MCP tools, and the knowledge contract that governs them.

## When to use

* Changing `mq-mcp/runtime/memory/obsidian_writer.py` or vault record schemas
* Adding or changing `brain_*` MCP tools in `server.py`
* Updating `docs/KNOWLEDGE_CONTRACT.md` or vault folder conventions
* Debugging vault resolution, frontmatter tagging, or record formatting

## When not to use

* Lesson capture, validation, or Ollama extraction — use `learn-engine-maintainer`
* Semantic memory packs or vector context — use `semantic-memory-maintainer`
* Review engine or review memory changes — use `review-runtime-maintainer`
* Generic tool safety work not specific to the vault — use `mcp-tool-safety-maintainer`

## Evals

### Should trigger

* "add a new record type to the second brain"
* "brain_record_decision writes the wrong frontmatter"
* "change the vault folder layout for sessions"
* "why does brain_status say the vault is missing?"

### Should not trigger

* "store a verified lesson from this review" → use `learn-engine-maintainer`
* "update the vector context docs" → use `semantic-memory-maintainer`
* "fix multi-pass review output" → use `review-runtime-maintainer`
* "audit write-capable tools generally" → use `mcp-tool-safety-maintainer`

## Core Files

* `mq-mcp/runtime/memory/obsidian_writer.py`
* `mq-mcp/server.py` brain-related MCP tools
* `docs/KNOWLEDGE_CONTRACT.md`
* `tests/test_obsidian_writer.py`

## Current Tool Surface

* `brain_status` — Class A, read-only vault status
* `brain_record_decision`, `brain_record_review`, `brain_record_session`, `brain_record_learning` — Class C, append-only vault writes
* `brain_promote_learning` — Class C, promotes a learning record

Verify the live list against `generated/tool-index.json` instead of trusting this section.

## Hard Boundaries

Per `docs/KNOWLEDGE_CONTRACT.md`, Obsidian is the passive knowledge store: it records, it never executes. The writer must stay:

* append-only to new date-stamped files — never edit or delete existing vault notes
* local-only — no sync, no push, no network
* explicit — no automatic background writes; callers gate on user approval
* schema-tagged — every record carries its schema version (`decision.v1`, `review.v1`, `session.v1`, `learn.v1`) in frontmatter
* scoped to the vault — `MQ_OBSIDIAN_DIR` or `~/mqobsidian`, never repo paths

HAL reads the vault, mq-agent orchestrates writes, mqlaunch only opens it. Keep that direction of flow.

## Change Rules

1. New record types get a schema version constant, a contract entry in `docs/KNOWLEDGE_CONTRACT.md`, and writer tests.
2. Keep vault resolution behind `_vault()` — no hardcoded user paths.
3. Keep `brain_*` tools thin wrappers over `obsidian_writer` functions; logic lives in the writer where it is testable.
4. Update `docs/TOOL_SAFETY.md` and `TOOL_INDEX.md` when the tool surface changes.
5. Sanitize titles and filenames; records may contain user-provided text.

## Verification

```bash
python -m compileall mq-mcp/runtime/memory/obsidian_writer.py -q
uv --directory mq-mcp run pytest ../tests/test_obsidian_writer.py -q
./scripts/check-mcp-tool-docs.sh
```

Run vault-writing tools against a temporary `MQ_OBSIDIAN_DIR` in tests — never the real vault.

## Review Standard

Lead with contract violations: writes outside the vault, edits to existing notes, background writes, missing schema tags, or execution behavior leaking into the knowledge store.
