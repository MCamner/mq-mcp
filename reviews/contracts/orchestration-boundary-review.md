# Review Contract: Orchestration Boundary Review

## Purpose

This contract governs orchestration boundary reviews produced by the mq-mcp review engine.

An orchestration boundary review detects when code in one MQ repo absorbs
responsibilities that belong to another repo. It enforces the declared
role division between mq-mcp, mq-agent, mq-hal, repo-signal, and mq-image-analyze.

---

## Hard Rules

### What the model MUST do

- Flag any tool or function in mq-mcp that does planning, routing, or multi-step
  orchestration (that belongs to mq-agent)
- Flag any tool that duplicates read-only repo analysis already owned by repo-signal
- Flag any tool that duplicates system status or report generation owned by mq-hal
- Flag any tool that absorbs visual perception or image processing (mq-image-analyze)
- Flag any auto-execution chain: a tool that calls another tool internally,
  building a workflow without human confirmation
- Use exact severity labels defined in this contract
- Cite the specific function and the repo that should own the behavior

### What the model MUST NOT do

- Modify any file
- Flag legitimate integration calls (e.g. mq-mcp calling mq-hal for a report is fine)
- Produce code quality or style findings
- Flag tool names as violations without evidence of boundary crossing in the implementation

---

## Severity Labels

```text
BOUNDARY — confirmed responsibility that belongs to another repo is implemented here
OVERLAP  — functionality duplicates another repo's declared scope; intent unclear
WARNING  — potential boundary drift: function is growing toward another repo's domain
NOTE     — informational: cross-repo call is a legitimate integration, boundary respected
```

No other labels are permitted in orchestration boundary reviews.

---

## Output Format

```
[SEVERITY] file_path:line_number
<one sentence naming the boundary and which repo should own the responsibility>
```

Example:

```
[BOUNDARY] mq-mcp/server.py:942
plan_next_action() builds a multi-step execution plan — planning logic belongs to mq-agent,
not mq-mcp which should only execute individual declared operations.

[OVERLAP] mq-mcp/server.py:1102
generate_repo_score() duplicates repo-signal's publish-readiness scoring;
mq-mcp should call repo_signal_analyze, not reimplement the scoring logic.

[WARNING] mq-mcp/server.py:2041
list_review_skills is growing toward skill management — ensure this stays
read-only introspection rather than routing logic.

[NOTE] mq-mcp/server.py:626
hal_repo_report() delegates to the mq-hal CLI via a fixed allowlist — correct
integration pattern, boundary respected.
```

---

## Scope

An orchestration boundary review covers:

- Planning and routing logic in mq-mcp (should be in mq-agent)
- Duplicated repo analysis or scoring (should be in repo-signal)
- Duplicated system status generation (should be in mq-hal)
- Visual or image processing (should be in mq-image-analyze)
- Auto-execution chains: tools that call other tools to build implicit workflows
- Class D tools whose subprocess calls bypass the declared allowlist

**Declared role division:**

| Repo               | Owns                                                          |
|--------------------|---------------------------------------------------------------|
| `mq-mcp`           | tool execution, safety enforcement, review engine, memory     |
| `mq-agent`         | planning, routing, multi-step orchestration, agent flows      |
| `mq-hal`           | system status, repo reports, operator summaries               |
| `repo-signal`      | repo health scoring, publish readiness, quality metrics        |
| `mq-image-analyze` | screenshot analysis, image reasoning, visual perception        |

An orchestration boundary review does NOT cover:

- Code quality or style
- Tool naming conventions
- Whether individual tools are correctly documented

---

## Invariants to enforce

```
mq-mcp tools must not contain planning or routing logic
mq-mcp tools must not reimplement repo-signal scoring
mq-mcp tools must not build multi-step execution chains internally
Integration calls to other repos must use declared integration points (not shell hacks)
Class D tools must not bypass the allowlist pattern used by hal_repo_report
```

---

## Limits

- Maximum 10 findings per file
- If no violations found: output `OK — no orchestration boundary violations detected.`

---

## Contract Version

```
version: 1.0
scope: orchestration-boundary-review
model-behavior: boundary-enforcement-only, no-code-changes
severity-labels: BOUNDARY, OVERLAP, WARNING, NOTE
max-findings: 10
```
