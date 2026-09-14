# Knowledge Contract — MQ Second Brain

Version: 0.2.0  
Owner: mq-mcp  
Vault: `~/mqobsidian`

---

## Role

Obsidian is the **passive knowledge store** for the MQ ecosystem.

It records what happened, what was decided, and what was learned.  
It does not execute, approve, or mutate system state.

```text
mq-mcp     → writes structured records to Obsidian
mq-agent   → orchestrates which records get written
HAL        → reads records, does not write
mqlaunch   → opens the vault, does not write
Obsidian   → displays and links — never runs anything
```

---

## Allowed writes

| Type | Folder | Writer |
| ---- | ------ | ------ |
| Architecture decisions | `decisions/` | mq-mcp obsidian_writer |
| Code review summaries | `reviews/` | mq-mcp obsidian_writer |
| Session notes | `sessions/` | mq-mcp obsidian_writer |
| Learned patterns | `learn/` | mq-mcp obsidian_writer |
| Manual notes | `inbox/` | human |

---

## Forbidden content

These must never appear in vault writes:

- Source code or executable scripts
- API keys, tokens, passwords, or credentials
- Commands intended to be run from the vault
- Release go/no-go decisions
- Destructive command approvals
- Content that bypasses mq-mcp schema validation

---

## Write rules

All writes from mq-mcp must:

1. Be **append-only** to new date-stamped files
2. Be **local-only** — no sync or push from within mq-mcp
3. Be **explicit** — no automatic background writes
4. Be **schema-validated** before writing
5. Include a `written_by`, `schema_version`, and `timestamp` header

---

## File naming

```text
decisions/YYYY-MM-DD-{slug}.md
reviews/YYYY-MM-DD-{slug}.md
sessions/YYYY-MM-DD-{slug}.md
learn/{pattern-name}.md
```

Dates are UTC ISO 8601 (`YYYY-MM-DD`).  
Slugs are kebab-case, max 40 characters, no special characters.

---

## Schema versions

| Schema | Used by | Fields |
| ------ | ------- | ------ |
| `decision.v1` | `record_decision()` | title, context, decision, rationale, consequences, tags |
| `review.v2` | `record_review()` | source, finding_count, top_risks, suggested_next_steps, confidence, ingress_decision |
| `session.v1` | `record_session()` | title, repos, summary, outcomes, follow_ups |
| `learn.v1` | `record_learning()` | pattern_name, pattern_type, summary, evidence, confidence |

---

## Ingress provenance

A review may arrive with the identity of the runtime that produced it and with
what the caller observed about this mq-mcp. `brain_record_review` decides
admission before anything is written:

| Payload | Outcome |
| ------- | ------- |
| an identity that fails `mq.runtime-identity.v1` | refused, nothing written |
| an observation of a different mq-mcp process than the one answering | refused, nothing written |
| no provenance at all | written, decision `accept_with_warning` |
| a receiver carrying findings, e.g. `RTP010` | written, decision `accept_with_warning` |
| verified producer and this runtime | written, decision `accept` |

`ingress_decision` appears in the frontmatter only when provenance was
supplied, and the decision, its reasons and any findings are written into a
`## Provenance` section of the note.

The writer moved from `review.v1` to `review.v2` when it gained the ability to
record provenance. The version describes the writer's contract, not which
optional fields a given record happened to carry, so every new review is
written as `review.v2` whether or not provenance was supplied — two shapes both
claiming `review.v1` would make the version useless for deciding what a reader
may expect. Existing `review.v1` files are valid and are never rewritten; a
reader that handles both sees provenance only on `v2`.

Absence is recorded as absence. A record with no producer identity says so
rather than carrying one inferred from the checkout, the latest tag, or the
runtime that happened to receive it.

mq-agent owns the comparison that produces RTP findings and their meaning. This
contract stores what it was told, plus the one check mq-mcp can make itself:
that the observation is about the process holding the record.

---

## HAL read policy

HAL may read from:

- `memory/`
- `decisions/`
- `learn/`
- `reviews/`

HAL may not:

- Write to any vault folder
- Create or delete vault files
- Modify decisions or learned patterns
- Approve actions based on vault content alone

---

## Ownership

This contract is owned by mq-mcp.  
Changes require a version bump and a commit to `mq-mcp/docs/KNOWLEDGE_CONTRACT.md`.  
No other repo may define what is written to the vault.
