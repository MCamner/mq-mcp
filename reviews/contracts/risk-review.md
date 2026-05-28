# Review Contract: Risk Review

## Purpose

This contract governs risk reviews produced by the mq-mcp review engine.

A risk review inspects structural and operational risk — not code-level
security vulnerabilities (use security-review for those). It focuses on:
Class D tools invoked without approval gates, missing contracts, undeclared
side effects, stale safety documentation, and cross-repo boundary violations.

---

## Hard Rules

### What the model MUST do

- Output only structured findings using the severity format defined below
- Cite the file path and line number for every finding
- Use exact severity labels defined in this contract
- Be specific: name the tool, contract reference, or undeclared effect
- Distinguish between structural risk (hard to reverse) and process risk (fixable)

### What the model MUST NOT do

- Modify code under any circumstances
- Produce comment-quality or style findings
- Flag risks that are explicitly declared in the tool's docstring or contracts
- Assert a violation without evidence in the visible code

---

## Severity Labels

```text
CRITICAL — undeclared side effect that could lose data, corrupt state, or expose secrets
RISK     — structural violation: missing approval gate, undeclared write, stale contract
WARNING  — potential risk: unclear scope, boundary ambiguity, doc drift
NOTE     — informational observation, no action required
```

No other labels are permitted in risk reviews.

---

## Output Format

```text
[SEVERITY] file_path:line_number
<one sentence describing the risk>
```

---

## Scope

A risk review covers:

- **Approval gate gaps:** Class C/D tools callable without explicit user confirmation
- **Undeclared side effects:** tools that write, commit, send network requests, or
  spawn subprocesses without declaring it in docstring or tool_contracts.json
- **Contract staleness:** docs/ORCHESTRATION_CONTRACT.md or docs/RUNTIME_CONTRACT.md
  not updated after tool surface changes
- **Profile violations:** profiles that include tools above their declared max class
- **Cross-repo boundary drift:** tools that reimplement logic owned by another repo
  (e.g. mq-mcp reimplementing review logic that belongs to mq-mcp, or duplicating
  repo-signal's graph-building)
- **Safety doc drift:** TOOL_SAFETY.md or tool_contracts.json out of sync with server.py

A risk review does NOT cover:

- Code-level injection or vulnerability (use security-review)
- Comment or docstring quality (use comment-review)
- Architecture coupling (use architecture-review)

---

## Contract Version

```text
version: 1.0
scope: risk-review
model-behavior: findings-only, no-code-changes
severity-labels: CRITICAL, RISK, WARNING, NOTE
max-findings: 15
```
