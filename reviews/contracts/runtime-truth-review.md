# Review Contract: Runtime Truth Review

## Purpose

This contract governs runtime truth reviews produced by the mq-mcp review engine.

A runtime truth review detects drift between the public signals that describe
the system and the actual runtime state. It covers version numbers, tool counts,
safety documentation coverage, and consistency between files that must agree.

It does not review code quality, naming, or architecture structure.

---

## Hard Rules

### What the model MUST do

- Identify every version number found in the file and state whether it matches VERSION
- Identify every tool count claim and state whether it matches the runtime tool list
- Flag every badge URL, release link, or version reference that is stale
- Report missing CHANGELOG entry if reviewing VERSION or README
- Report docs/stability.json mismatch if version does not match VERSION
- Use exact severity labels defined in this contract
- Cite the specific string that is drifted, not just the concept

### What the model MUST NOT do

- Modify any file
- Comment on code quality, naming, or style
- Flag things that are intentionally versioned differently (e.g. pyproject.toml minor)
- Assert drift without showing the conflicting values explicitly

---

## Severity Labels

```text
DRIFT    — confirmed mismatch between two public signals (version, count, link)
WARNING  — potential drift: value is suspicious but cannot be confirmed without runtime data
STALE    — a reference, badge, or link points to an older version or release
NOTE     — informational: version found, consistent with expected value
```

No other labels are permitted in runtime truth reviews.

---

## Output Format

```
[SEVERITY] file_path:line_number
<one sentence naming the drifted values and where they conflict>
```

Example:

```
[DRIFT] README.md:4
Version badge shows 1.3.0 but VERSION file contains 1.9.0.

[STALE] README.md:4
Release link points to /releases/tag/v1.3.0 — no GitHub release exists for this tag.

[DRIFT] README.md:17
Tool count says 76 but runtime discovers 91 @mcp.tool decorators in server.py.

[NOTE] docs/stability.json:3
version field is 1.9.0 — consistent with VERSION.
```

---

## Scope

A runtime truth review covers:

- Version numbers: VERSION file, README badge, README release link, CHANGELOG entry,
  docs/stability.json, pyproject.toml version field
- Tool counts: all "N tools" references in README and docs vs. runtime @mcp.tool count
- Safety doc coverage: whether tool count in TOOL_SAFETY.md matches runtime
- Release links: badge URLs, GitHub release tags, shield.io badge version strings
- CHANGELOG: whether the current version has a dated entry

A runtime truth review does NOT cover:

- Code correctness or quality
- Architecture or naming
- Whether the release itself is production-ready

---

## Invariants to enforce

```
VERSION == README badge version
VERSION == README release link version
VERSION == CHANGELOG latest entry
VERSION == docs/stability.json version
runtime tool count == README tool count claims
runtime tool count == TOOL_SAFETY.md tool count
```

If any of these are false, emit a DRIFT finding.

---

## Limits

- Maximum 10 findings per file
- If no drift is found: output `OK — no runtime truth drift detected.`

---

## Contract Version

```
version: 1.0
scope: runtime-truth-review
model-behavior: drift-detection-only, no-code-changes
severity-labels: DRIFT, WARNING, STALE, NOTE
max-findings: 10
```
