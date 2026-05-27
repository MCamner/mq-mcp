# Review Pipeline

This document describes the full execution path of `review_file` — from tool invocation to structured output and memory persistence.

---

## Overview

### Single-pass mode (default)

```text
review_file(relative_path, mode)
  │
  ├── 1. Path safety          resolve_repo_file(path)
  ├── 2. Contract loading     reviews/contracts/{mode}-review.md
  ├── 3. Architecture context review_engine/context/architecture_map.json
  ├── 4. Skill routing        review_engine/review_router.route_file(path)
  ├── 5. Memory context       review_engine/review_memory.format_past_context(path)
  ├── 6. Model call           OpenAI chat.completions (system + user prompt)
  ├── 7. Severity parsing     review_engine/severity_engine.parse_findings(raw)
  ├── 8. Output formatting    severity_engine.format_summary(findings, path)
  └── 9. Memory persistence   review_engine/review_memory.save(...)
```

### Deep mode (`deep=True`)

```text
review_file(relative_path, mode, deep=True)
  │
  ├── 1–5. Same as single-pass (path safety, contract, arch context, skill, memory)
  │
  ├── 6a. Pass 1 — Structure analysis
  │       MultiPassReviewer.structure_pass()
  │       → compact summary: responsibility, patterns, hotspots, review focus
  │       → max 400 tokens, no findings
  │
  ├── 6b. Pass 2 — Review pass
  │       MultiPassReviewer.review_pass()
  │       → same contract + skill + memory context as single-pass
  │       → structure summary injected as ## Structure analysis
  │       → max 2048 tokens
  │
  ├── 7. Severity parsing     review_engine/severity_engine.parse_findings(raw)
  ├── 8. Output formatting    severity_engine.format_summary(findings, path)
  └── 9. Memory persistence   review_engine/review_memory.save(...)
```

Deep mode costs ~2x API calls but gives the model explicit structural grounding
before it starts reviewing. The structure pass is cheap (400 tokens) and its
output is used solely as context for the review pass — it is not returned.

---

## Stage 1 — Path safety

`resolve_repo_file(relative_path)` is called first. This rejects:

- absolute paths
- `../` traversal
- anything outside `REPO_ROOT`

If the path is blocked, `review_file` returns an error immediately. No API call is made.

---

## Stage 2 — Contract loading

`_load_review_contract(mode)` loads `reviews/contracts/{mode}-review.md`.

The contract is the single source of truth for the model's behavior:

- output format (`[SEVERITY] file:line\nbody`)
- allowed severity labels
- max findings per review
- scope rules (what to flag, what to skip)
- uncertainty handling

If the requested mode has no contract, falls back to `comment-review.md`. If no contract exists at all, the tool returns an error without calling the model.

Available contracts:

| Mode | Contract file | Severity labels |
| --- | --- | --- |
| `comment` | `comment-review.md` | NOTE, SUGGESTION, WARNING, MISSING |
| `architecture` | `architecture-review.md` | NOTE, SUGGESTION, WARNING, ARCHITECTURE, RISK |
| `security` | `security-review.md` | NOTE, WARNING, RISK |

---

## Stage 3 — Architecture context

`_load_architecture_role(relative_path)` reads `review_engine/context/architecture_map.json` and looks up the file's declared architecture role (e.g., `"MCP server — tool registry and HTTP endpoints"`).

The role string is injected into the user prompt as `Architecture role: ...`. This gives the model grounding: it knows whether it is reviewing a server entry point, a test helper, or a config file.

If the map is missing or the file has no entry, this stage is silently skipped.

Rebuild with: `build_repo_context()` MCP tool or `python review_engine/repo_context_builder.py`.

---

## Stage 4 — Skill routing

`review_engine/review_router.route_file(relative_path)` returns `(skill_name, skill_content)`.

Skills are file-type-specific guidance injected into the system prompt. They do not override the contract — they supplement it with context the contract cannot anticipate (e.g., Python docstring conventions, shell quoting rules, MCP tool naming patterns).

Current routing rules:

| Condition | Skill |
| --- | --- |
| Path ends with `server.py` | `mcp-tool-review` |
| Extension `.py` | `python-comment-review` |
| Extension `.sh` | `shell-review` |
| No match | no skill injected |

If routing fails (import error or missing skill file), the review continues without a skill.

---

## Stage 5 — Memory context

`review_engine/review_memory.ReviewMemory.format_past_context(relative_path)` loads the most recent review entry for the file and formats the top 5 findings as a context block.

This block is injected into the user prompt under `## Previous review context`. It tells the model:

- when the last review was
- which mode was used
- how many findings there were
- what the top findings said

This prevents the model from re-flagging already-known issues and enables incremental quality improvement across reviews.

If no history exists for the file, this stage is silently skipped.

Storage: `review_engine/memory/review_history.json` (local JSON, max 10 entries per file).

---

## Stage 6 — Model call

The system and user prompts are assembled and sent to OpenAI.

System prompt structure:

```text
You are a code review engine operating under a strict review contract.
Follow the contract exactly. Do not deviate from the output format.
Do not modify code. Output only structured review findings.

{contract}

## Skill: {skill_name}

{skill_content}
```

User prompt structure:

````text
Review this file under the contract above.

File: {relative_path}
Architecture role: {arch_role}

## Previous review context

{past_findings}

```
{file_content}
```
````

Model: `OPENAI_MODEL` env var, defaults to `gpt-4.1-mini`. Max tokens: 2048.

---

## Stage 7 — Severity parsing

`review_engine/severity_engine.parse_findings(raw)` parses the model's raw output into structured `Finding` objects.

Expected format from model:

```text
[SEVERITY] file:line
One-sentence description of the finding.
```

Each finding is parsed into:

```python
@dataclass
class Finding:
    severity: Severity   # NOTE / SUGGESTION / WARNING / MISSING / ARCHITECTURE / RISK
    location: str        # e.g. "mq-mcp/server.py:105"
    body: str            # the finding sentence
```

Findings are sorted by severity (RISK > ARCHITECTURE > WARNING > MISSING > SUGGESTION > NOTE) then by line number.

Blocking findings: any finding with severity WARNING, RISK, or ARCHITECTURE is considered blocking. `has_blocking_findings(findings)` returns True if any exist.

---

## Stage 8 — Output formatting

`severity_engine.format_summary(findings, file_path)` produces the final human-readable output returned by the MCP tool:

```text
Review: mq-mcp/server.py (comment mode)
17 findings  [NOTE=8  SUGGESTION=5  WARNING=3  MISSING=1]

[WARNING] mq-mcp/server.py:270
Missing try/finally around tty handle — handle leaks on exception.

[SUGGESTION] mq-mcp/server.py:110
...
```

If the severity engine fails to parse (e.g., model produced non-conforming output), the raw model response is returned as-is.

---

## Stage 9 — Memory persistence

`review_engine/review_memory.ReviewMemory.save(...)` writes the review result to local history.

Stored per entry:

- `file_path` — repo-relative path
- `mode` — review mode (comment, architecture, security)
- `timestamp` + `timestamp_iso` — Unix time and ISO 8601
- `model` — model string used
- `skill` — skill name routed to
- `finding_count` — total findings
- `severity_counts` — `{NOTE: N, WARNING: N, ...}`
- `findings_text` — formatted output (used as context in future reviews)

Max 10 entries per file. Oldest entries are discarded.

---

## MCP tools

| Tool | What it does |
| --- | --- |
| `review_file` | Runs the full pipeline for a file |
| `build_repo_context` | Rebuilds architecture_map.json and file_summary_index.json |
| `list_review_contracts` | Lists available review modes |
| `list_review_history` | Summary of all reviewed files and last review |
| `get_last_review` | Full findings from the last review for a specific file |

---

## Key files

| Path | Role |
| --- | --- |
| `reviews/contracts/` | Review contracts (mode → rules) |
| `reviews/skills/` | File-type-specific guidance |
| `reviews/golden/` | Reference examples for expected output quality |
| `review_engine/repo_context_builder.py` | Builds architecture_map.json and file_summary_index.json |
| `review_engine/review_router.py` | Routes files to skills |
| `review_engine/severity_engine.py` | Parses and sorts findings |
| `review_engine/review_memory.py` | Persistent review history |
| `review_engine/context/architecture_map.json` | Generated: file → architecture role |
| `review_engine/context/file_summary_index.json` | Generated: file → public symbols |
| `review_engine/memory/review_history.json` | Generated: per-file review history |
