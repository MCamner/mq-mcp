---
name: release-readiness
description: Use when preparing mq-mcp for release by checking versioning, changelog, tool docs, safety docs, tests, validation scripts, generated docs, and Git state.
---

# Release Readiness

Use this skill before tagging, publishing, announcing, or merging release-critical mq-mcp changes.

## When to use

- Before tagging, publishing, or announcing a mq-mcp release
- After completing a milestone to verify version alignment, tool docs, and CI status
- When the release checklist needs a structured pass

## When not to use

- Regular development or feature work not bound for immediate release
- Diagnosing a specific tool failure — use `mcp-tool-safety-maintainer`
- Docs-only updates — use `docs-maintainer`

## Evals

### Should trigger

- "is mq-mcp ready to release?"
- "check mq-mcp tool contracts and safety before tagging"
- "what's blocking the mq-mcp v2.0.0 release?"
- "run the mq-mcp release checklist"

### Should not trigger

- "update mq-mcp docs" → use `docs-maintainer`
- "fix the Bridget bridge" → use `bridget-bridge-maintainer`
- "check a specific tool safety issue" → use `mcp-tool-safety-maintainer`
- "regular mq-mcp feature work" → only needed at release boundaries

## Always Inspect

- `git status --short`
- `VERSION`
- `mq-mcp/pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `ROADMAP.md`
- `docs/TOOL_SAFETY.md`
- `TOOL_INDEX.md`
- `docs/integration.md`
- `scripts/validate.sh`
- `scripts/release-check.sh`
- `.github/workflows/`

## Release Risks

Block release on:

- version mismatch between `VERSION`, `mq-mcp/pyproject.toml`, README badge, and changelog
- stale tool counts or undocumented MCP tools
- failing safety or integration checks
- missing tests for path safety or write-capable tool changes
- generated docs/assets drifting unintentionally
- dirty worktree containing unrelated user changes
- secrets, `.env`, private local paths, or credentials in tracked files
- lockfile changes that were not intentional

## Verification

Run:

```bash
./scripts/release-check.sh
```

If that is too broad for the current change, use:

```bash
./scripts/validate.sh
uv --directory mq-mcp run pytest ../tests -q
python -m compileall mq-mcp/ -q
```

For tool changes, also run:

```bash
./scripts/check-mcp-tool-docs.sh
./scripts/check-integration-smoke.sh
./scripts/check-bridge-tool-discovery.sh
```

## Release Closure

The order below is what `v2.1.0` followed. Each step exists because skipping it
produced a defect.

### 1. Inventory before writing anything

Renaming `Unreleased` to a version heading is not closure. Compare the history
against the changelog first:

```bash
git log <previous tag>..HEAD --oneline
```

Every user-, contract-, safety- or runtime-visible change must have an entry.
At `v2.1.0` the existing `Unreleased` described 5 of 33 commits: the Keychain
credential model, runtime identity, the routing tools, effect-based tool
gating, finding verification and the stdin fix had all landed unrecorded.
Tagging on that changelog would have published notes that are wrong at the
moment they become permanent.

### 2. Move every version surface together

Nine surfaces, not four. A partial bump is how `v2.0.1` shipped known-bad:

```text
VERSION
mq-mcp/pyproject.toml
.mq/repo-contract.json
docs/stability.json
docs/tool_contracts.json     # regenerate: scripts/generate_tool_contracts.py
mq-mcp/uv.lock               # regenerate: cd mq-mcp && uv lock
README.md                    # version badge
ROADMAP.md
CHANGELOG.md                 # ## [X.Y.Z] - YYYY-MM-DD
```

### 3. Make ROADMAP true

No stale `planned`, `partial`, or wrong release label may survive if the work
is done. If the next scope is undecided, write that. Inventing a version to
fill the field is how a roadmap starts lying.

### 4. Local gates

```bash
./scripts/validate.sh            # includes the test suite
./scripts/check-tool-contracts.sh
./scripts/check-stability.py
./scripts/check-skills.sh
./release-check.sh --json        # root, not scripts/ — see below
./scripts/release-notes.sh vX.Y.Z
```

`release-notes.sh` must return the whole section and exit 0. It exits non-zero
for missing (3) and oversized sections rather than publishing a truncated one.

Confirm `git status --porcelain` is empty after the suite runs.

### 5. Release-closure PR, then tag the merge

Scope is version surfaces, changelog closure, README status, roadmap truth and
generated metadata. No feature rides along.

Require green on the exact PR head. A green job is not proof the check you care
about ran — read the step output when a gate matters.

Merge first, then tag the squash-merge commit. A tag created before the merge
points at a commit that squashing discards; macos-scripts `v2.2.0` sits on such
an orphan today.

```bash
git switch main && git fetch origin && git merge --ff-only origin/main
cat VERSION                      # confirm before tagging
git tag -s -a vX.Y.Z -m "vX.Y.Z — <theme>"
git push origin vX.Y.Z
```

Signing is already configured in this environment (`gpg.format=ssh`,
`user.signingkey`, `tag.gpgsign=true`), so `-s` needs no extra flags.

### 6. Do not publish by hand

The tag is the release. `release.yml` triggers on `v*`, reads notes through
`scripts/release-notes.sh` and calls `gh release create --verify-tag`. Running
`gh release create` yourself races the workflow. A themed title afterwards is
fine:

```bash
gh release edit vX.Y.Z --title "vX.Y.Z — <theme>"
```

### 7. Final proof

```bash
git rev-list -n 1 vX.Y.Z         # == the release-closure merge commit
git tag -v vX.Y.Z                # good signature
gh release view vX.Y.Z           # published, notes == the CHANGELOG section
git status --short                # empty
```

### Which release-check

`./release-check.sh` at the root is read-only and conforms to
`repo_release_check.v1`. `scripts/release-check.sh` exports the tool registry,
which is a write; the root script deliberately does not call it. Use the root
one for a readiness verdict.

## Report Format

Return:

- status: ready, blocked, or uncertain
- blockers
- changed files
- checks run
- checks skipped and why
- next concrete action
