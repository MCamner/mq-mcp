# Semantic Memory Policy

## Purpose

Semantic memory is a curated knowledge store for durable, reusable context.
It is not a log, not a cache, and not a summary buffer.

Every entry must be worth keeping across versions.

---

## What may be stored

- Stable facts about the system: tool counts, resolver names, safety class definitions
- Decisions that are not obvious from the code: why a boundary was drawn, why a tool is Class C
- Conventions that are enforced but not documented elsewhere
- Doc summaries that save repeated reading: README summary, ROADMAP phase status
- Cross-repo contracts: what mq-agent expects from mq-mcp, what mq-hal reports

## What may NOT be stored

- Transient state: open PR numbers, current branch name, in-progress work
- Ephemeral facts: "last review was on date X", "CI was green today"
- Duplicate content already in architecture_memory/ (ADRs live there, not here)
- Per-file review history (that lives in review_engine/memory/)
- Secrets, credentials, or API keys
- Machine-generated dumps without editorial judgment

---

## Required fields

Every entry must have:

| Field        | Type                                                    | Required |
|--------------|---------------------------------------------------------|----------|
| `key`        | string, kebab-case, globally unique                     | yes      |
| `content`    | string, plain text, describes the fact or decision      | yes      |
| `type`       | one of: fact, decision, convention, summary, warning    | yes      |
| `source`     | where the fact was derived (file path or doc name)      | yes      |
| `tags`       | list of strings for search routing                      | recommended |
| `version`    | mq-mcp version when the entry was created/last verified | recommended |
| `confidence` | high, medium, or low                                    | recommended |
| `created_at` | Unix timestamp                                          | auto      |
| `updated_at` | Unix timestamp                                          | auto      |

An entry without `source` is unsourced and should be treated as unverified.
An entry without `type` is unclassified and cannot be routed correctly.

---

## Entry types

| Type         | Meaning                                                                 |
|--------------|-------------------------------------------------------------------------|
| `fact`       | A verifiable claim about the current system state                       |
| `decision`   | A recorded design decision with reasoning (use ADR for structural ones) |
| `convention` | A pattern that is enforced but not described in code                    |
| `summary`    | A condensed description of a large document or module                   |
| `warning`    | A known risk or constraint that reviewers must be aware of              |

---

## How old entries are marked

An entry is considered stale when:

- Its `version` field is more than one minor version behind the current VERSION
- Its content references a fact that has demonstrably changed (different tool count, renamed tool)
- Its `source` file has changed significantly since the entry was created

Stale entries should be updated, not silently deleted.
If the fact no longer applies, update with a note explaining why it was superseded.

---

## How conflicts are handled

When two entries contradict each other:

1. Prefer the entry with the higher `confidence` value
2. If confidence is equal, prefer the most recently updated entry
3. Flag both entries with the `memory-hygiene-review` contract
4. Resolve by updating one entry and noting the resolution

Do not silently overwrite a conflicting entry.

---

## How items are replaced

Use `store_semantic_memory(key=..., content=...)` with the same key to update.
The `created_at` timestamp is preserved; `updated_at` is refreshed.

Replacing an entry resets its content but keeps its history.
If the entry's meaning has changed substantially, prefer a new key and deprecate the old one.

---

## How sources are cited

`source` should be one of:

- A repo-relative file path: `README.md`, `docs/TOOL_SAFETY.md`
- A doc name: `ORCHESTRATION_CONTRACT.md`, `RUNTIME_CONTRACT.md`
- A convention name: `ADR-003`, `BND-001`
- For bootstrap entries: `bootstrap:README.md`

`source` must not be empty, `"unknown"`, or `"manual"` without a note in the content.

---

## How bootstrap may be used

`bootstrap_semantic_memory` ingests key docs as `summary` entries.
Bootstrap is idempotent: it skips entries whose source content has not changed.

Bootstrap must not overwrite entries with:

- type=decision
- type=convention
- type=warning
- confidence=high

Bootstrap may overwrite entries with type=summary if the source doc has changed.

---

## How stale memory is detected

Run `mq-mcp memory audit` to see:

- Entries missing `source`
- Entries missing `type`
- Entries whose `version` is more than one minor behind VERSION
- Entries with duplicate content
- Entries without any tags (not searchable)

---

## Key naming convention

Keys must be kebab-case and globally unique within the store.

Recommended prefixes:

| Prefix          | Use for                                              |
|-----------------|------------------------------------------------------|
| `mq-mcp.*`      | Facts about this repo's own structure and behavior   |
| `mq-agent.*`    | Facts about mq-agent's expected interface            |
| `mq-hal.*`      | Facts about mq-hal's reported structure              |
| `repo-signal.*` | Facts about repo-signal's scoring or output          |
| `doc.*`         | Summaries of specific documentation files            |

---

## Policy version

```yaml
version: 1.0
last-updated: 2026-05-31
```
