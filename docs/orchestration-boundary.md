# Orchestration Boundary

`mq-mcp` is the local execution runtime for MQ engineering workflows. It owns
the MCP tool surface, safety classes, path boundaries, review engine, and local
memory stores.

It does not plan multi-step work. That is the orchestrator's job.

For the formal contract, see `docs/ORCHESTRATION_CONTRACT.md`.

## Role Map

| Repo | Use it for | Do not use it for |
| --- | --- | --- |
| `mq-mcp` | Local MCP tools, path-safe repo access, safety metadata, review, memory, bridge execution | Planning workflows, deciding task order, UI-heavy reporting |
| `mq-agent` | Planning, orchestration, routing, dry-run, approval gates, agent flows | Reimplementing review heuristics, severity scoring, architecture reasoning, risk classification |
| `mq-hal` | Operator status, reports, environment checks, high-level local assistant summaries | Owning MCP tool safety or repo review contracts |
| `repo-signal` | Read-only repo health, publish readiness, scoring, metadata exports | Mutating repos or acting as the MCP runtime |
| `mq-image-analyze` | Visual perception, screenshots, diagrams, image reasoning | General repo review or orchestration |

## When To Use mq-mcp

Use `mq-mcp` when a caller needs one bounded action with a declared tool
contract:

- read repo files or git state
- inspect tool safety metadata
- run a review through the review engine
- query or update local semantic, review, architecture, or learning memory
- invoke a documented local integration tool
- validate that runtime contracts still match implementation

Use `mq-agent` when the task requires deciding which tools to call, sequencing
work, presenting dry-runs, or asking the user for approval.

Use `repo-signal` when the task is repository scoring, readiness, or read-only
analysis that should stay outside the MCP runtime.

Use `mq-hal` when the task is operator-facing status, reports, or environment
summary.

## Automation Rules

| Tool class | Automatic use | Approval required |
| --- | --- | --- |
| Class A | Yes, for repo-scoped read-only work | No |
| Class B | Yes, if the caller accepts declared external/read-only access | No |
| Class C | No | Yes, because it writes local files |
| Class D | No | Yes, because it opens apps or runs subprocesses |

Review tools may call OpenAI when configured. Callers should treat those as
explicit review actions even when the tool is Class A.

## Agent Decision Rules

An agent should choose `mq-mcp` only when all of these are true:

- the requested action maps to a named MCP tool
- the input path is repo-relative or inside an allowed root
- the tool safety class is acceptable for the current approval state
- the caller can consume a string result or documented structured text

An agent should not choose `mq-mcp` when it needs to:

- commit, push, tag, or merge
- choose a release strategy
- score repo health locally instead of calling `repo-signal`
- duplicate review severity, risk, architecture, or drift logic outside
  `mq-mcp`
- maintain hidden session state across tool calls

## Boundary Examples

| Request | Correct owner |
| --- | --- |
| "Read `README.md` and summarize safety notes." | `mq-mcp` |
| "Plan the safest order to fix three repos." | `mq-agent` |
| "Run publish readiness scoring." | `repo-signal` via direct CLI or mq-mcp proxy |
| "Review this diff for architecture drift." | `mq-mcp` review engine |
| "Open the repo in Terminal after confirmation." | `mq-agent` approval, then `mq-mcp` Class D tool |
| "Explain current local environment status." | `mq-hal` |

## Profile Guidance

Profiles in `profiles/` are client templates, not runtime enforcement. The
client must still enforce approval gates.

- `read-only.json` is the default for inspection.
- `repo-only.json` is for repo-scoped reads and controlled writes.
- `mq-agent.json` is for orchestration clients that need discovery and safety
  metadata before invoking tools.
- `developer.json` and `local-macos.json` may expose Class C/D tools and should
  only be used in trusted local sessions.

Run these checks after changing the boundary:

```bash
./scripts/check-profiles.py
./scripts/validate.sh
```
