# Review Contract: Architecture Review

## Purpose

This contract governs architecture reviews produced by the mq-mcp review engine.

An architecture review inspects module boundaries, responsibility separation,
coupling, and consistency between documentation and runtime behavior.
It does not modify code. It does not review comment quality or naming style.

---

## Hard Rules

### What the model MUST do

- Output only structured findings using the severity format defined below
- Cite the file path and line number (or file path alone for file-level findings)
- Use the exact severity labels defined in this contract
- Identify the specific boundary, contract, or assumption being violated
- Distinguish between observed behavior and documented intent
- Express uncertainty explicitly: "unclear whether X" rather than asserting X

### What the model MUST NOT do

- Modify code under any circumstances
- Produce comment-style or naming-style findings (use comment-review for those)
- Generate executable patches or diffs
- Speculate about performance or scalability without evidence in the file
- Repeat the same finding more than once

---

## Severity Labels

Every finding must start with exactly one of these labels:

```text
NOTE          — factual observation about structure, no action required
SUGGESTION    — optional architectural improvement, low priority
WARNING       — coupling or boundary issue that increases maintenance risk
ARCHITECTURE  — structural violation: wrong layer, wrong owner, wrong scope
RISK          — active safety, security, or correctness risk in current design
```

No other labels are permitted in architecture reviews.

---

## Output Format

Each finding must follow this exact structure:

```text
[SEVERITY] file_path:line_number
<one sentence describing the finding>
```

For file-level findings with no specific line:

```text
[SEVERITY] file_path
<one sentence describing the finding>
```

Example:

```text
[ARCHITECTURE] mq-mcp/bridge.py:302
known_local_repos duplicates repo-registry logic from server.py — this logic
has one owner and one file; bridge.py is importing an env var it does not own.

[WARNING] mq-mcp/server.py
review_file calls the OpenAI API directly inside an MCP tool; the API client
instantiation is inside the tool function, making it impossible to mock or
swap in tests without patching the import.

[RISK] mq-mcp/server.py:1490
review_file constructs a system prompt by embedding the full contract text and
skill text directly into a string — no length guard. A very large contract or
skill file would silently send an oversized prompt.

[NOTE] mq-mcp/bridge.py
bridge.py is the orchestration layer between the MCP server and OpenAI.
Its role is clear but it currently also owns Bridget identity rendering
(show_bridget_face, scramble_print) — two distinct responsibilities in one file.
```

---

## Scope

An architecture review covers:

- Module responsibility boundaries (does this file own what it does?)
- Duplication of logic across files (who owns the truth?)
- Coupling between layers (does layer A reach into layer B's internals?)
- Consistency between documentation and runtime (does README match the code?)
- Safety boundaries (path resolvers, subprocess guards, API key handling)
- Entry point clarity (is the public interface obvious?)

An architecture review does NOT cover:

- Comment or docstring quality (use comment-review)
- Naming conventions (use comment-review)
- Performance or scalability
- Test coverage

---

## Uncertainty

If the reviewer cannot determine whether a structural choice is intentional:

```text
[NOTE] mq-mcp/bridge.py:302
known_local_repos is defined in both bridge.py and server.py with identical
logic — unclear whether this is intentional isolation or accidental duplication.
```

Do not assert duplication is a bug if the motivation might be deliberate isolation.

---

## Limits

- Maximum 15 findings per file
- Skip findings about code that is clearly experimental or marked TODO
- If a file has no findings: output `OK — no architecture review findings.`

---

## Contract Version

```yaml
version: 1.0
scope: architecture-review
model-behavior: structure-only, no-code-changes
severity-labels: NOTE, SUGGESTION, WARNING, ARCHITECTURE, RISK
max-findings: 15
```
