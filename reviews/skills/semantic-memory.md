# Skill: Semantic Memory Maintainer

This skill is injected when reviewing files under `semantic_memory/`.

## Ownership

`semantic_memory/store.json` is the only persistent store in this module.
No other files are written by semantic memory tools.

## Key invariants

- `store.json` is append/update only — no automatic purge.
- Keys must be stable across calls; changing a key orphans old data.
- `format_context_block()` must return an empty string (not raise) when
  the store is absent or empty.
- `bootstrap_semantic_memory` is idempotent — running it twice must not
  duplicate entries.

## What to flag in reviews

- Writes to any location outside `semantic_memory/store.json`
- Non-idempotent bootstrap logic
- `search()` returning different results for identical queries (non-deterministic ranking)
- Missing fallback when store.json does not exist
