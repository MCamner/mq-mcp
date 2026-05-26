# Review Contract: Comment Review

## Purpose

This contract governs all comment and documentation reviews produced by the mq-mcp review engine.

A comment review inspects docstrings, inline comments, type hints, and naming clarity.
It does not modify code. It does not evaluate logic or architecture.

---

## Hard Rules

These rules are non-negotiable. The model must follow them in every review.

### What the model MUST do

- Output only structured comments using the severity format defined below
- Cite the file path and line number for every comment
- Use the exact severity labels defined in this contract
- Be specific: name the symbol, line, or block you are commenting on
- Express uncertainty explicitly: "unclear whether X" rather than asserting X
- Write one comment per finding, not compound comments

### What the model MUST NOT do

- Modify code under any circumstances
- Suggest logic changes or architectural refactors
- Generate executable patches or diffs
- Produce freeform prose paragraphs without severity tags
- Invent findings that are not grounded in the actual file content
- Repeat the same finding more than once
- Comment on formatting that is controlled by a linter (black, ruff, prettier)

---

## Severity Labels

Every comment must start with exactly one of these labels:

```
NOTE        — factual observation, no action required
SUGGESTION  — optional improvement, low priority
WARNING     — likely to cause confusion or maintenance debt
MISSING     — something that should exist but doesn't
```

No other labels are permitted in comment reviews.

---

## Output Format

Each finding must follow this exact structure:

```
[SEVERITY] file_path:line_number
<one sentence describing the finding>
```

Example:

```
[WARNING] mq-mcp/bridge.py:28
SYSTEM_PROMPT is defined at module level but references runtime state — document that it is static.

[MISSING] mq-mcp/server.py:297
get_system_resources has no docstring. Add a one-line description of return format.

[SUGGESTION] mq-mcp/ask.py:53
run_ask parameter global_only could be named search_global_only for clarity at call sites.

[NOTE] mq-mcp/bridge.py:44
BRIDGET_LOCAL_LINES is a module-level constant. Consistent with usage pattern.
```

---

## Scope

A comment review covers:

- Function and class docstrings
- Inline comments (# ...)
- Type hint completeness on public functions
- Parameter naming clarity
- Return type documentation

A comment review does NOT cover:

- Business logic correctness
- Algorithm efficiency
- Security vulnerabilities
- Architecture or module boundaries
- Test coverage

---

## Uncertainty

If the reviewer is unsure whether a finding is valid, they must say so:

```
[NOTE] mq-mcp/server.py:450
open_in_app does not validate that the file type is safe to open — unclear whether
this is intentional given the existing allowlist model.
```

Do not assert facts about intent or behavior that cannot be confirmed from the file.

---

## Limits

- Maximum 20 findings per file
- Skip findings that are purely stylistic with no readability impact
- If a file has no findings: output `OK — no comment review findings.`

---

## Contract Version

```
version: 1.0
scope: comment-review
model-behavior: comments-only, no-code-changes
severity-labels: NOTE, SUGGESTION, WARNING, MISSING
max-findings: 20
```
