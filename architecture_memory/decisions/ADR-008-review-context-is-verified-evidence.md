---
id: ADR-008
title: Review context is consumed as verified evidence, not a raw file read
date: 2026-09-14
status: accepted
area: review, evidence, repo-context
---

## Decision

The review pipeline consumes repo context through a validating loader that
reports what it verified. It does not read context JSON directly.

Two representations exist and they are not interchangeable:

- `review_engine/context/architecture_map.json` is **builder-internal**. It is
  the intermediate output of `repo_context_builder.py` and the input to
  `generated_artifacts.py`. No review consumer may read it.
- `generated/architecture/architecture_map.json` (schema `architecture_map.v1`)
  is the **canonical persisted review-context evidence**. It carries `schema`,
  `repo_name`, `generated_at`, `file_count`, and `files`.

No new schema is introduced. `architecture_map.v1` is sufficient.

Failure is split by kind, following the ingress rule frozen in
`docs/KNOWLEDGE_CONTRACT.md`: a mismatch is a warning, a self-contradiction is
a refusal.

- **Refused** — the artifact is not what it claims to be: wrong `schema`, wrong
  `repo_name`, unparseable JSON, malformed `files` shape, or a file path that
  escapes the repo root. A refused artifact contributes nothing to the prompt.
- **Degraded** — the artifact is what it claims to be, but its reach is
  limited: `generated_at` is old, coverage is partial, or an entry names a file
  that no longer exists. A degraded artifact is used, and its limits are
  reported.
- **Missing** — no artifact. Review proceeds without architecture context and
  says so.

In every case the status is visible in review output. Absent context is
acceptable; context presented as more current or more complete than it is, is
not.

## Rationale

Measured against `459854f` before any change:

```text
generated/architecture/architecture_map.json   consumers: 0
review_engine/context/architecture_map.json    consumers: 2 review paths
review_engine/context/file_summary_index.json  consumers: 0
```

The canonical artifact is write-only. `build_repo_context()` produces it and
nothing reads it. `_load_architecture_role()` and
`_build_rich_cross_file_context()` both read the builder-internal flat map.

That flat map is committed and was last rebuilt on 2026-05-29. Comparing it to
a fresh scan with the builder's own rules:

```text
committed entries         174
fresh scan                280
entries whose file is gone  20
files never mapped         126
entries whose role changed   0
```

The failure mode is therefore **silent incompleteness, not false labelling**.
Role heuristics are path-based, so a surviving file's role does not drift.
Nothing shipped since May carries a role: `brain_ingress.py`,
`runtime/memory/obsidian_writer.py`, `release_gate/`, ADR-006, ADR-007,
`docs/KNOWLEDGE_CONTRACT.md`, and `schemas/vendor/` are all invisible to review
context.

This is why staleness degrades rather than refuses. Refusing a 174-entry
artifact for age would discard 154 correct entries to avoid 20 dangling ones,
and would not address the 126 that were never there. Refusal is reserved for
artifacts that misrepresent their own identity, because that is the failure
that cannot be reported honestly to the operator.

Two provenance weaknesses had to be closed before the fields could carry this
weight:

- `repo_name` was `repo_root.name`, the directory name. In a git worktree it
  reports the worktree's directory, so an equality check against the repo name
  refuses valid evidence. `.mq/repo-contract.json` carries a committed,
  worktree-stable `repo` identity and is the correct source.
- `generated_at` is accurate in the production flow: `build_repo_context()`
  runs the builder subprocess first, then enriches the map it just wrote, so
  the timestamp describes a scan that did just happen. The weakness is the
  `flat_arch_map=None` branch, which reads whatever flat map is on disk —
  possibly the committed one from May — and stamps it with the current time.
  No production caller takes that branch today, so this is a latent trap rather
  than a current falsehood. It is closed by scanning instead of reading, so the
  field is true by construction rather than true by caller discipline.

The old drift check compared the artifact's filesystem mtime against
`server.py`'s. That answers whether one file is older than another. It does not
answer whether the evidence is current or belongs to this repo. `generated_at`
is the provenance; mtime is not.

## Consequences

- A fresh clone has no canonical artifact — `generated/*.json` is gitignored.
  Review then runs without architecture context and reports the reason, instead
  of silently injecting a committed map from an earlier quarter. One
  `build_repo_context()` call restores it, now with full coverage.
- The committed flat map stays in git as the builder's intermediate. It is no
  longer review evidence.
- Review output exposes the context source, its age, and its verification
  status. This is the review-side counterpart of ADR-007 precondition 1.
- Cross-repo, malformed, and future-dated context fail closed rather than being
  hidden behind an empty-string return.

## Related

- ADR-007 — no implicit git fallback for learn context
- ADR-004 — review contracts drive output
- `docs/KNOWLEDGE_CONTRACT.md` — ingress decision vocabulary
