# Review Contract: Release Readiness Review

## Purpose

This contract governs release readiness reviews produced by the mq-mcp review engine.

A release readiness review identifies blockers that would prevent a clean, safe
release. It checks version sync, documentation completeness, safety coverage,
and CI signals. It does not review code correctness.

---

## Hard Rules

### What the model MUST do

- Check whether the version in the reviewed file matches VERSION
- Check whether CHANGELOG has a dated entry for the current version
- Check whether README tool count matches the runtime count
- Check whether docs/stability.json version matches VERSION
- Flag any `[ ]` (unchecked) item in a release checklist section
- Flag any reference to a TODO, FIXME, or placeholder that would block release
- Use exact severity labels defined in this contract
- Be specific: quote the stale value and the expected value

### What the model MUST NOT do

- Modify any file
- Flag work-in-progress items that are clearly future scope
- Comment on code quality or style
- Assert a blocker without quoting the specific text that is wrong

---

## Severity Labels

```text
BLOCKER  — this must be fixed before release: version mismatch, missing CHANGELOG entry,
           failing CI signal, empty required section
WARNING  — this should be reviewed before release: stale reference, unchecked checklist item,
           doc section that describes an old state
NOTE     — informational: value found, consistent with release readiness
```

No other labels are permitted in release readiness reviews.

---

## Output Format

```text
[SEVERITY] file_path:line_number
<one sentence identifying the blocker or warning and what must be done>
```

Example:

```text
[BLOCKER] README.md:4
Version badge shows 1.3.0 but current VERSION is 1.9.0 — badge must be updated before release.

[BLOCKER] CHANGELOG.md
No entry found for version 1.9.0 — CHANGELOG must have a dated entry before release.

[WARNING] ROADMAP.md:1135
Phase 3 has unchecked items — confirm these are deferred scope, not release blockers.

[NOTE] docs/stability.json:3
version field 1.9.0 matches VERSION — consistent with release.
```

---

## Scope

A release readiness review covers:

- Version sync: VERSION, README badge, README release link, CHANGELOG entry,
  docs/stability.json, docs/tool_contracts.json mq_mcp_version
- Documentation completeness: no empty required sections, no placeholder text
- Checklist items: any `[ ]` box in release-related sections
- CI signals: README CI badge, any mention of failing checks
- Safety coverage: whether all tools are documented in TOOL_SAFETY.md

A release readiness review does NOT cover:

- Code quality or correctness
- Architecture or design decisions
- Future roadmap items or deferred scope

---

## Invariants to enforce

```text
All version surfaces agree (VERSION, README, CHANGELOG, stability.json, tool_contracts.json)
CHANGELOG has a dated entry for the current version
README CI badge is green (Validate badge)
No [ ] boxes in release checklist sections
No FIXME or placeholder text in release-critical docs
```

---

## Limits

- Maximum 10 findings per file
- If no blockers found: output `OK — no release readiness blockers detected.`

---

## Contract Version

```yaml
version: 1.0
scope: release-readiness-review
model-behavior: blocker-detection-only, no-code-changes
severity-labels: BLOCKER, WARNING, NOTE
max-findings: 10
```
