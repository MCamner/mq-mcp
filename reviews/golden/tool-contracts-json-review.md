# Golden Review: docs/tool_contracts.json — JSON Mode

This is a reference example of a high-quality JSON review of a contract/metadata
file. It demonstrates correct severity labeling for schema consistency, maintenance
hazard detection, and the expected depth for a versioned API contract file.

---

## Review output

```text
[WARNING] docs/tool_contracts.json:3
"mq_mcp_version": "1.0.0" is hardcoded. This field will silently drift as
releases happen. Nothing enforces that this value is bumped when VERSION changes.
A CI check or release script should assert that mq_mcp_version matches VERSION,
or the field should be treated as informational with a note that it requires
manual sync.

[SUGGESTION] docs/tool_contracts.json:9
Three tool descriptions are written in Swedish ("Analyserar en CSV-fil inom
repo-katalogen.", line 9; "Analyserar en Guitar Pro-fil (GP3, GP4, GP5).",
line 19; "Läser innehållet i en fil inom repo-katalogen.", line 349) while all
other descriptions are in English. This is a naming inconsistency inside a
machine-readable contract file. External consumers parsing descriptions will
encounter mixed-language output. Standardize to English.

[NOTE] docs/tool_contracts.json:10
The "resolver" field is free-text with no declared vocabulary. Values range
from "resolve_repo_file" and "resolve_allowed_local_file" (function names) to
"REPO_ROOT (AST + file reads)" and "REPO_ROOT/docs/architecture/" (path
descriptions). A consumer trying to programmatically classify tools by resolver
cannot reliably parse this field. Consider defining a controlled vocabulary
(e.g., "repo_file", "allowed_local", "none", "custom") with a prose description
field for the exception cases.

[NOTE] docs/tool_contracts.json:14
All 61 tools have "examples": []. The field exists in every tool entry but is
never populated. An empty examples array adds no information and signals that
the field was planned but never implemented. Either populate representative
examples for the highest-value tools (review_file, build_repo_context) or
remove the field from the schema to reduce noise.

[NOTE] docs/tool_contracts.json:2
The side_effects vocabulary is undeclared. Values like "writes-review-engine-context",
"review_memory_write", "openai_api_call", "clipboard-write" appear ad-hoc across
entries. Without a declared enum, new tools can introduce values that are
semantically equivalent to existing ones (e.g., "file-write" vs
"writes-review-engine-context"). Add a comment block or companion schema
document that enumerates the allowed side_effects values.
```

---

## Why this review is correct

**mq_mcp_version drift (line 3):** This file is read by CI and validation scripts
to verify tool contract consistency. If the version field drifts, the file
appears authoritative but describes the wrong release. The problem is not that
the field exists — it is that there is no enforcement. The fix is a one-line
assertion in release-check.sh: `grep -q "\"mq_mcp_version\": \"$(cat VERSION)\""`.

**Swedish descriptions (lines 9, 19, 349):** The contract file is consumed
programmatically by bridge.py and potentially by external MCP clients. Mixed-language
descriptions produce inconsistent tool discovery output. The three Swedish entries
are likely early tool definitions that predated the English convention. This is
a SUGGESTION rather than WARNING because it does not break functionality — but
it will confuse any consumer that processes descriptions.

**Free-text resolver field (line 10):** The resolver field exists to document
which path safety function a tool uses. When it becomes a narrative prose field
("REPO_ROOT (AST + file reads)"), it can no longer be parsed programmatically.
The tool-safety reviewer and drift detector both need to know which resolver a
tool uses — a controlled vocabulary makes this trivially checkable. This is NOTE
rather than WARNING because the current entries are individually accurate; the
issue is structural.

**Empty examples (line 14):** An empty array is schema noise. It occupies space
in every tool entry (61 × `"examples": []`) without conveying information. The
two highest-leverage tools to add examples for are `review_file` (shows the
mode/deep parameters) and `build_repo_context` (shows the expected output shape).

**Undeclared side_effects vocabulary (line 2):** Side effects are the primary
signal for whether a tool is safe to call without user confirmation. An
undeclared vocabulary means two tools with equivalent risk profiles may have
different labels — "file-write" vs "writes-review-engine-context" — making
automated safety analysis unreliable. This is a structural debt that grows with
each new tool.

---

## What was deliberately excluded

- Key ordering — JSON objects are order-independent; the current ordering
  (name, class, description, resolver, write, subprocess, side_effects, examples)
  is consistent and readable
- Indentation style — 2-space throughout, no mixed indentation
- The schema_version: "tool-contracts.v1" format — informative and stable
- Boolean fields (write, subprocess) — consistently typed as booleans throughout
- tool_count: 61 — matches the actual tools array length (verified)
- Individual tool descriptions (beyond the Swedish issue) — accurate

---

## Metadata

```text
file: docs/tool_contracts.json
mode: comment
contract: comment-review v1.0
skill: json-review
findings: 5
severity-distribution: WARNING=1, SUGGESTION=1, NOTE=3
```
