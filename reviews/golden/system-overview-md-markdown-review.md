# Golden Review: docs/architecture/SYSTEM_OVERVIEW.md — Markdown Mode

This is a reference example of a high-quality markdown review of an architecture
document. It demonstrates correct severity labeling, maintenance-hazard detection,
and the expected precision for doc-vs-runtime drift findings.

---

## Review output

```text
[WARNING] docs/architecture/SYSTEM_OVERVIEW.md:58
"53 tools as of v1.1" is stale. The current server.py registers 61 tools.
This count will mislead any reviewer or tool that reads this doc as ground truth.
Update the count or replace with a reference to the authoritative source
(docs/TOOL_SAFETY.md summary table).

[WARNING] docs/architecture/SYSTEM_OVERVIEW.md:128
review_router.py file responsibilities list only names .py and .sh routing.
Markdown (.md) and JSON (.json) skills were added in Phase 3 and are now
active. The routing table is incomplete and will mislead a developer adding
a new file type.

[WARNING] docs/architecture/SYSTEM_OVERVIEW.md:145
The review engine pipeline diagram shows a 5-step linear flow ending at
severity_engine.parse_findings(). The current pipeline has 7 steps:
past context load (review_memory), cross-file context build (callgraph_builder
+ architecture_map), ContextSelector budget cap, deep/single-pass branch
(MultiPassReviewer or direct call), and review memory save after the model call.
A reader using this diagram will not understand how context is assembled or
why deep mode exists.

[MISSING] docs/architecture/SYSTEM_OVERVIEW.md:111
File responsibilities section documents 7 files but omits 5 that are now central
to the review pipeline: review_memory.py (persistent finding store),
multi_pass_reviewer.py (4-pass orchestrator), drift_detector.py (contract
verifier), callgraph_builder.py (import graph + cross-file context),
context_selector.py (budget-capped context prioritizer). Any reader trying to
understand the review system from this doc will have an incomplete picture.

[NOTE] docs/architecture/SYSTEM_OVERVIEW.md:5
"Last updated: 2026-05-27" is a static date. Once the document drifts, this
line gives a false sense of freshness. Consider using detect_architecture_drift
or review_architecture_doc to flag staleness rather than relying on a manual
update date.
```

---

## Why this review is correct

**Stale tool count (line 58):** Architecture documents that quote tool counts
become stale every time a tool is added or removed. This document is used by
the drift detector as a ground-truth reference, so a wrong count here will
cause false positives or false negatives in automated checks. The fix is either
to update the number or replace it with a cross-reference: "see docs/TOOL_SAFETY.md
for the current count."

**Incomplete routing table (line 128):** The review_router section is part of
the "file responsibilities" contract. When a developer adds a new file type and
consults this doc to understand how routing works, the incomplete list will lead
them to believe only `.py` and `.sh` are routed. In reality `.md` and `.json`
also have skills. The omission is not just incomplete — it's actively misleading.

**Stale pipeline diagram (line 145):** The diagram is a teaching artifact —
it exists specifically to explain the system to newcomers and reviewers. A diagram
that shows the 2024-era pipeline when the 2026 pipeline has 7 steps creates real
onboarding debt. The cross-file context injection and ContextSelector are not
optional extras — they are the core of how context quality is maintained.

**Missing file responsibilities (line 111):** review_memory.py alone handles
persistent state across reviews — it is not a detail. drift_detector.py is
the tool that reads this very document to check for contract violations. Its
absence from the doc it audits is ironic and gap-creating.

**Static date (line 5):** A date field is better than nothing, but the pattern
of manually updating it guarantees it will be wrong. The system now has
detect_architecture_drift and review_architecture_doc specifically to catch
this kind of staleness. Noting the pattern here is low-stakes but valuable
calibration for how this doc should be maintained.

---

## What was deliberately excluded

- ASCII diagram style — the box-and-arrow art is correct and readable; no
  formatting finding needed
- "What mq-mcp is" and "What this system is NOT" sections — accurate and stable
- Table formatting (pipe-style) — consistent throughout the document
- The REPO_ROOT definition at line 174 — correct and precise
- Environment variable table — entries are accurate; MQ_MCP_SERVER_COMMAND
  and MQ_MCP_SERVER_ARGS are present and correct
- Safety class table — matches docs/TOOL_SAFETY.md

---

## Metadata

```text
file: docs/architecture/SYSTEM_OVERVIEW.md
mode: markdown
contract: comment-review v1.0
skill: markdown-review
findings: 5
severity-distribution: WARNING=3, MISSING=1, NOTE=1
```
