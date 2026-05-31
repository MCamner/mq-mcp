# Learning Model

The learning model defines the shape and lifecycle of verified engineering lessons in `mq-mcp`.

## Record lifecycle

```text
observe session/review/diff
→ capture verified lesson
→ redact secrets
→ validate schema
→ append local JSONL record
→ search/summarize later
→ optionally dry-run promote to docs/guidance
```

## Record fields

| Field | Purpose |
| --- | --- |
| `id` | Stable local learning identifier. |
| `repo` | Repository the lesson applies to. |
| `source` | Origin: `codex`, `claude`, `mq-agent`, `mq-hal`, `manual`, `review`, or `diff`. |
| `task` | Short task name. |
| `lesson` | The reusable lesson. |
| `problem` | Optional description of what was wrong. |
| `solution` | Optional description of what fixed it. |
| `files_touched` | Optional file list. |
| `commands_used` | Optional command list. |
| `validation` | Evidence that the solution worked. |
| `tags` | Search/filter tags. |
| `risk` | `low`, `medium`, `high`, or `unknown`. |
| `promoted_to` | Guidance targets this lesson has been promoted to. |
| `created_at` | UTC timestamp. |

## Example

```json
{
  "id": "learn_20260531_094500_0001",
  "repo": "mq-mcp",
  "source": "codex",
  "task": "Fix tool-count drift",
  "lesson": "Keep README, TOOL_SAFETY, tool_contracts.json and runtime tool count in sync before release.",
  "problem": "README and safety docs described different tool counts.",
  "solution": "Add release-check coverage for tool count consistency.",
  "files_touched": ["README.md", "docs/TOOL_SAFETY.md", "docs/tool_contracts.json"],
  "commands_used": ["./scripts/validate.sh", "./scripts/release-check.sh"],
  "validation": ["validate passes", "release-check passes"],
  "tags": ["release", "tool-contract", "docs-drift"],
  "risk": "low",
  "promoted_to": [],
  "created_at": "2026-05-31T09:45:00Z"
}
```

## Query behavior

Search is deterministic keyword search across the serialized JSON payload. It does not require an API key or embeddings.

## Promotion behavior

The first implementation only generates promotion previews. This avoids accidental mutation of guidance files and keeps the safety contract simple.

Future promotion may write to guidance files, but only with explicit confirmation and tests proving it cannot write outside allowed repo paths.
