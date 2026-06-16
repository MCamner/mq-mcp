---
name: curate-learn-inbox
description: Use when reviewing, drafting, promoting, or clearing pending learn candidates in the inbox queue — the preview-first inbox -> record_learning curation flow.
---

# Curate Learn Inbox

Operational skill for turning auto-extracted learn candidates into curated
lessons. The post-commit hook queues grounded candidates in
`learn_engine/memory/inbox.jsonl`; this skill drives the review path that
promotes the worthwhile ones into the curated store without ever auto-writing.

The governing rule is **preview first, never auto-write**. Validation is always
a `MANUAL VALIDATION REQUIRED` placeholder until a human confirms the evidence —
auto-filling it as truth is a failure mode, not a shortcut.

## When to use

* Reviewing what is pending in the learn inbox
* Producing a review-ready `record_learning` draft from a candidate
* Promoting a verified candidate into the curated store
* Clearing a candidate from the inbox after promotion or a deliberate skip

## When not to use

* Changing the mapping logic, schemas, or storage itself — use `learn-engine-maintainer`
* Writing records to the Obsidian vault — use `brain-maintainer`
* Generic tool safety or path-resolver work — use `mcp-tool-safety-maintainer`

## Flow

1. **List** — `learn_inbox` shows pending candidates (reads the queue only).
2. **Preview** — `learn_inbox_preview` (select by `commit` prefix and/or
   `pattern_name`; must match exactly one) returns a draft with
   `task` / `lesson` / `validation` / `risk` / `repo` / `source` / `tags`.
   Writes nothing.
3. **Verify** — confirm the evidence by hand, generalize an over-local lesson,
   and replace the `validation` placeholder with the real verification. This is
   the approval gate; do not skip it.
4. **Promote** — call `record_learning` with the verified fields. This is the
   only step that writes `learn_engine/memory/lessons.jsonl`.
5. **Clear** — `learn_inbox_drop` (`apply=True`) removes the candidate's row
   from the inbox. Never touches the curated store.

## Invariants

* Preview and drop never write `learn_engine/memory/lessons.jsonl`.
* Promotion is always a human decision; `validation` is never auto-filled.
* Zero or multiple selector matches abort with no write.

## Core Files

* `mq-mcp/learn_engine.py` — `build_record_learning_draft`, `preview_inbox_candidate`, `drop_inbox_candidate`
* `mq-mcp/server.py` — `learn_inbox`, `learn_inbox_preview`, `learn_inbox_drop` tools
* `learn_engine/memory/inbox.jsonl` — pending queue
* `learn_engine/memory/lessons.jsonl` — curated store
* `tests/test_learn_inbox_preview.py`
* `tests/test_learn_inbox_drop.py`
* `RUNBOOK.md` — "Learn inbox curation (SOP)" section

## Evals

### Should trigger

* "what's in the learn inbox?"
* "draft a record_learning entry for the release-gate-v2 candidate"
* "preview the inbox candidate before I promote it"
* "I promoted that candidate, drop it from the inbox"

### Should not trigger

* "add a tag field to the learning record schema" → use `learn-engine-maintainer`
* "record this decision in the second brain" → use `brain-maintainer`
* "audit the path resolvers in server.py" → use `mcp-tool-safety-maintainer`
