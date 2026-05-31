# Review Contract: Memory Hygiene Review

## Purpose

This contract governs memory hygiene reviews produced by the mq-mcp review engine.

A memory hygiene review inspects the semantic memory store and architecture
memory for entries that are stale, unsourced, contradictory, redundant, or
incorrectly scoped. It helps keep curated knowledge accurate over time.

---

## Hard Rules

### What the model MUST do

- Flag entries that reference a version older than the current version by more than one minor
- Flag entries without a source field or with source="unknown"
- Flag entries whose content contradicts another entry with higher confidence
- Flag duplicate entries that describe the same fact with different keys
- Flag entries that describe transient state (e.g. "current PR is open") not permanent knowledge
- Use exact severity labels defined in this contract
- Cite the entry key for every finding

### What the model MUST NOT do

- Delete or modify any entry
- Flag entries that are correctly marked as superseded or historical
- Assert staleness without comparing to an available version reference
- Produce code quality or style findings

---

## Severity Labels

```text
STALE      — entry references an old version or describes state that no longer holds
UNSOURCED  — entry has no source field or source cannot be verified
CONFLICT   — entry contradicts another entry; both cannot be true
REDUNDANT  — entry duplicates another entry with identical or near-identical content
SCOPE      — entry stores transient state (a PR number, a TODO) that belongs elsewhere
NOTE       — informational: entry looks correct and well-sourced
```

No other labels are permitted in memory hygiene reviews.

---

## Output Format

```
[SEVERITY] memory_key
<one sentence describing the hygiene issue>
```

Example:

```
[STALE] mq-mcp.tool-count
Entry says "76 tools" but server.py currently has 91 @mcp.tool decorators.

[UNSOURCED] mq-mcp.review-engine-design
source field is empty — cannot verify whether this reflects current architecture.

[CONFLICT] mq-mcp.safety-class-model and mq-mcp.safety-class-model-v2
Both describe Class A definition but give conflicting resolver rules.

[REDUNDANT] mq-mcp.validation-flow and mq-mcp.ci-validation
Both describe the validate.sh flow with nearly identical content.

[SCOPE] mq-mcp.current-open-pr
Stores "PR #4 is open" — transient state, not durable knowledge.

[NOTE] mq-mcp.tool-safety-model
Well-sourced from TOOL_SAFETY.md, describes stable classification model.
```

---

## Scope

A memory hygiene review covers:

- Version-bound claims that may have become stale
- Entries missing a source (where was this fact derived from?)
- Entries with low confidence that conflict with higher-confidence entries
- Near-duplicates (same fact, different keys)
- Transient state stored as if it were permanent knowledge
- Bootstrap entries that duplicate content already in docs

A memory hygiene review does NOT cover:

- Whether the described facts are correct (that requires runtime verification)
- Code quality or architecture
- Entry formatting or naming conventions beyond the key name

---

## Invariants to enforce

```
Every memory item must have a non-empty source field
No two items should describe the same fact with contradictory values
Items that reference a version should match the current VERSION
Items describing transient state (PR numbers, TODO notes) should be flagged
```

---

## Limits

- Maximum 15 findings per review
- If no hygiene issues found: output `OK — semantic memory hygiene looks good.`

---

## Contract Version

```
version: 1.0
scope: memory-hygiene-review
model-behavior: hygiene-detection-only, no-modifications
severity-labels: STALE, UNSOURCED, CONFLICT, REDUNDANT, SCOPE, NOTE
max-findings: 15
```
