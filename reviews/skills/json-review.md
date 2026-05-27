# Skill: JSON Review

Apply this guidance when reviewing JSON configuration, contract, or metadata files.

## What to check

**Schema and structure**

- Are required top-level keys present and consistently named?
- Are values the correct type (string vs. number vs. boolean vs. array)?
- Are arrays that should be non-empty actually non-empty?
- Are there duplicate keys (valid JSON, but usually a bug)?

**Naming consistency**

- Are keys named consistently (snake_case or camelCase — not mixed within the same object)?
- Do key names match the naming convention used elsewhere in the repo for the same concept?

**Completeness**

- Are optional fields that carry important semantics present (e.g., `description`, `version`)?
- Are enum-valued string fields using values from the declared set?
- Are paths relative or absolute consistently — and correctly for how they will be resolved?

**Maintenance hazards**

- Are tool counts, version strings, or other numbers hardcoded that should be derived?
- Are file paths that reference other repo files still valid?
- Are there TODO or placeholder values (e.g., `"TBD"`, `""`, `null`) in non-optional fields?

**Format**

- Is indentation consistent (2 or 4 spaces — not mixed)?
- Are trailing commas present (invalid JSON)?
- Are there unnecessary escape sequences?

## What to skip

- Key ordering — JSON is order-independent and reordering is not a bug.
- Aesthetic preferences about spacing within values.
- Minification vs. pretty-print style — that's a tooling concern.

## Severity guidance

| Severity | Use for |
| --- | --- |
| NOTE | Naming inconsistency, minor structural anomaly |
| SUGGESTION | Missing optional but important field, unclear placeholder |
| WARNING | Wrong type, missing required field, stale value |
| MISSING | Required key or section absent |
