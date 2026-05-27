# Skill: Markdown Review

Apply this guidance when reviewing Markdown documentation files.

## What to check

**Structure and navigation**

- Is there a clear top-level heading that matches the file's purpose?
- Are heading levels used consistently (no skipped levels)?
- Do long documents have a table of contents or obvious navigation?

**Content completeness**

- Are code examples fenced with a language specifier (```python, ```bash, etc.)?
- Are commands shown without a language specifier when the type is ambiguous?
- Do links point to valid targets within the repo, not external URLs that may rot?
- Are placeholder values clearly marked (e.g., `<your-value>`, `YOUR_KEY`)?

**Maintenance hazards**

- Does the file reference version numbers, tool counts, or other values that drift?
  Flag any hardcoded count or version that should be derived or cross-referenced.
- Does the file say "coming soon", "TODO", or "planned" without a tracking reference?
- Are there duplicate sections or stale headings that no longer match the content?

**Format correctness**

- Are blank lines missing before or after fenced code blocks?
- Are list items inconsistently formatted (mixed `-` and `*` bullets)?
- Are there trailing spaces or hard-wrapped lines that impede diffs?

## What to skip

- Line length violations — prose naturally runs long.
- Minor phrasing preferences.
- Stylistic choices that don't affect correctness or maintenance.
- Grammar pedantry unless it causes genuine ambiguity.

## Severity guidance

| Severity | Use for |
| --- | --- |
| NOTE | Style inconsistency, minor clarity issue |
| SUGGESTION | Missing context, unclear placeholder, no language specifier |
| WARNING | Stale value that will mislead (wrong count, wrong version) |
| MISSING | Required section absent (setup steps, prerequisites, examples) |
