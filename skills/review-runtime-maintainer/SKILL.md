---
name: review-runtime-maintainer
description: Use when changing mq-mcp review engine code, review contracts, review skills, severity parsing, multi-pass review, review memory, architecture memory, repo context selection, or review MCP tools.
---

# Review Runtime Maintainer

Use this skill for mq-mcp's central cognition runtime.

## When to use

* Changing review engine code, review contracts, severity parsing, multi-pass review, or review memory
* Adding new review skills or updating golden review tests
* Debugging why review output, architecture memory, or repo context selection is wrong

## When not to use

* Orchestrating review calls from mq-agent — use the mq-agent `mq-mcp-review-orchestration` skill
* Adding new non-review MCP tools — use `mcp-tool-safety-maintainer`
* Semantic memory changes unrelated to review — use `semantic-memory-maintainer`
* Learning engine or lesson storage changes — use `learn-engine-maintainer`
* Bridge or Bridget changes — use `bridget-bridge-maintainer`

## Evals

### Should trigger

* "severity parsing puts everything at medium"
* "add a new review contract for security passes"
* "review_diff picks the wrong repo context"
* "update the golden reviews after the output format change"

### Should not trigger

* "orchestrate reviews from mq-agent" → use the mq-agent `mq-mcp-review-orchestration` skill
* "add a screenshot tool" → use `mcp-tool-safety-maintainer`
* "store a verified lesson from this review" → use `learn-engine-maintainer`
* "fix Bridget tool discovery" → use `bridget-bridge-maintainer`

## Core Files

* `review_engine/`
* `reviews/contracts/`
* `reviews/skills/`
* `reviews/golden/`
* `docs/architecture/REVIEW_PIPELINE.md`
* `docs/architecture/SYSTEM_OVERVIEW.md`
* `docs/RUNTIME_CONTRACT.md`
* `mq-mcp/server.py` review-related MCP tools
* `tests/` review, observability, contract and drift tests

## Ownership Rule

mq-mcp owns review logic, contracts, severity normalization, semantic review memory, architecture memory, repo context selection, risk analysis and MCP exposure.

It should consume repo-signal symbolic exports when available, but should not duplicate full repo indexing, metrics dashboards, terminal UI, or workflow orchestration.

## Change Workflow

1. Identify whether the change affects contracts, skills, context, memory, MCP tool surface, or docs.
2. Keep output shapes deterministic and contract-driven.
3. Update the relevant review contract or skill before changing prompt assembly behavior.
4. Update golden reviews when expected output changes intentionally.
5. Update architecture docs if boundaries, passes, or context sources change.
6. Add or adjust focused tests for parsing, routing, memory, drift, or tool metadata.

## Risk Checks

Check for:

* unbounded raw file injection into prompts
* findings without severity normalization
* stale tool count or safety metadata
* review tools that mutate files unexpectedly
* architecture reasoning leaking into mq-agent or repo-signal
* silent failure when repo-signal exports are unavailable

## Verification

Prefer focused checks first:

```bash
uv run pytest tests/test_server_observability.py -q
uv run pytest tests -q
./scripts/release-check.sh
```

Use the broad release check after tool-surface or contract changes.
