---
name: learn-engine-maintainer
description: Use when changing the mq-mcp learning engine, `learn_*` or `ollama_learn_*` tools, learning schemas, lesson storage, the Ollama provider, or learning contract docs.
---

# Learn Engine Maintainer

Use this skill for mq-mcp's deterministic learning layer: lesson capture, validation, storage, and the local Ollama extraction provider.

## When to use

* Changing `mq-mcp/learn_engine.py`, learning schemas, or lesson storage behavior
* Adding or changing `learn_*`, `learning_*`, or `ollama_learn_*` MCP tools
* Changing the Ollama provider, extraction prompts, or structured-output validation
* Updating learning contract docs or learning-related release gate checks

## When not to use

* Writing records to the Obsidian vault — use `brain-maintainer`
* Review engine or review memory changes — use `review-runtime-maintainer`
* Semantic memory packs or vector context — use `semantic-memory-maintainer`
* Generic tool safety work not specific to learning — use `mcp-tool-safety-maintainer`

## Evals

### Should trigger

* "add a new field to the learning record schema"
* "learn_from_review is storing lessons without validation"
* "make ollama_learn_extract fall back gracefully when Ollama is down"
* "tighten the prompt-injection guards in the learn engine"

### Should not trigger

* "record this decision in the second brain" → use `brain-maintainer`
* "fix severity parsing in reviews" → use `review-runtime-maintainer`
* "rebuild the semantic memory pack" → use `semantic-memory-maintainer`
* "audit path resolvers in server.py" → use `mcp-tool-safety-maintainer`

## Core Files

* `mq-mcp/learn_engine.py`
* `mq-mcp/providers/ollama_provider.py`
* `mq-mcp/server.py` learn-related MCP tools
* `schemas/learning.schema.json`
* `schemas/learn_extraction.schema.json`
* `learn_engine/memory/lessons.jsonl`
* `docs/LEARNING_CONTRACT.md`
* `docs/LEARNING_MODEL.md`
* `docs/LEARN_CONTRACT.md`
* `docs/LEARN_OLLAMA.md`
* `docs/OLLAMA_PROVIDER.md`
* `mq-mcp/release_gate/checks.py` learning contract checks
* `tests/test_learn_engine.py`
* `tests/test_learn_alias_tools.py`
* `tests/test_learn_extract_from_last_review.py`
* `tests/test_learn_hygiene.py`
* `tests/test_ollama_learn_extract.py`
* `tests/test_ollama_learn_status.py`

## Hard Boundaries

The learning layer is local-only and non-executing. Per `docs/LEARNING_CONTRACT.md`, lessons may inform reviews, runbooks, and agent guidance, but learning code must never:

* execute commands or mutate router policy, allowlists, or run commands
* store secrets — keep `_SECRET_PATTERNS` scrubbing intact
* accept prompt-injection content — keep `_PROMPT_INJECTION_PATTERNS` gating intact
* let the Ollama provider make release decisions, approve destructive actions, or handle secrets
* auto-store extractions — `should_store` gating stays caller-controlled

## Change Rules

1. Validate every stored record against `schemas/learning.schema.json` or `schemas/learn_extraction.schema.json`.
2. Keep allowed sources, risks, pattern types, and promotion targets as explicit allowlists in `learn_engine.py`.
3. Keep Ollama failures graceful: unavailable or invalid output must degrade, not crash or silently store.
4. Update `docs/LEARNING_CONTRACT.md` and `docs/LEARNING_MODEL.md` when storage shape or boundaries change — the release gate checks these files exist.
5. Add focused tests for new validation, scrubbing, or fallback behavior.

## Verification

```bash
python -m compileall mq-mcp/learn_engine.py mq-mcp/providers/ollama_provider.py -q
uv --directory mq-mcp run pytest \
  ../tests/test_learn_engine.py \
  ../tests/test_learn_alias_tools.py \
  ../tests/test_learn_hygiene.py \
  ../tests/test_ollama_learn_extract.py \
  ../tests/test_ollama_learn_status.py \
  -q
./scripts/check-mcp-tool-docs.sh
```

Ollama-dependent paths must pass tests without a running Ollama instance.

## Review Standard

Lead with contract violations: executing behavior, secret leakage, injection-gate bypasses, schema-less storage, or Ollama output trusted without validation. Treat a lesson stored without verification metadata as a bug.
