# Skill: Review Engine Maintainer

This skill is injected when reviewing files under `review_engine/`.

## Ownership

mq-mcp owns all review logic. Files in `review_engine/` must not duplicate
logic from mq-agent, repo-signal, or other ecosystem repos.

## Key invariants

- `severity_engine.py` is the single source of truth for severity labels.
  Any label added here must also appear in `reviews/contracts/*.md` and
  `docs/RUNTIME_CONTRACT.md` severity ordering.
- `review_router.py` must not contain review logic — only routing decisions.
- `drift_detector.py` checks are numbered sequentially. New checks must
  increment the counter and be documented in the module docstring.
- `review_memory.py` never commits — it only writes `review_history.json`.
- `callgraph_builder.py` must remain idempotent: repeated calls should
  produce the same output given the same repo state.

## Change checklist

- [ ] If you add a severity level: update `SEVERITY_ORDER`, `has_blocking_findings`,
  `reviews/contracts/` affected contracts, and `docs/RUNTIME_CONTRACT.md`.
- [ ] If you add a drift check: increment check number, update module docstring.
- [ ] If you add a context source: update `ContextSelector` priority docs.
- [ ] If you change `ReviewMemory`: verify it never commits.

## What to flag in reviews

- New severity labels not declared in a contract
- Context assembly that bypasses `ContextSelector`
- Writes to locations outside `review_engine/memory/` or `review_engine/context/`
- Functions that make API calls not guarded by OPENAI_API_KEY check
