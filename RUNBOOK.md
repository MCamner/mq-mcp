# mq-mcp Runbook

## Install

```bash
cd mq-mcp
uv sync
```

## Run entry point

```bash
uv run python main.py
```

## Run MCP server

```bash
uv run mcp run server.py
```

## Run bridge

```bash
uv run python bridge.py "List the available MCP tools."
```

## Validate from repo root

```bash
./scripts/validate.sh
```

## Run tests

```bash
uv --directory mq-mcp run pytest ../tests -v
```

## Learn inbox curation (SOP)

Turn an auto-extracted candidate into a curated lesson. Preview-first: nothing
is written until a human confirms the draft and calls `record_learning`.

1. **List** pending candidates — `learn_inbox`. Reads
   `learn_engine/memory/inbox.jsonl` only.
2. **Preview** one candidate — `learn_inbox_preview` (select by `commit` SHA
   prefix and/or `pattern_name`; must match exactly one). Returns a review-ready
   draft (`task`/`lesson`/`validation`/`risk`/`repo`/`source`/`tags`). Writes
   nothing. `validation` is always a `MANUAL VALIDATION REQUIRED` instruction —
   never an auto-filled truth claim.
3. **Verify** the draft by hand: confirm the evidence, generalize the lesson if
   it is too local, and replace `validation` with the real verification once
   checked. This step is the approval gate — do not skip it.
4. **Promote** — call `record_learning` with the verified fields. This is the
   only step that writes the curated store (`lessons.jsonl`).
5. **Clear** the candidate — `learn_inbox_drop` (`apply=True`) to remove its row
   from the inbox queue. Never touches the curated store.

Invariants: preview and drop never write `lessons.jsonl`; promotion is always a
human decision; zero/multiple selector matches abort with no write.

## Release check

Review:

* git status
* VERSION
* CHANGELOG.md
* README.md
* validation result
* tests
* docs
* secrets
