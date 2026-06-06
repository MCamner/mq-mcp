---
name: docs-maintainer
description: Use when keeping mq-mcp README, GitHub Pages docs, installation guides, demo docs, safety docs, tool docs, changelog, roadmap, or semantic docs consistent with code.
---

# Docs Maintainer

Keep mq-mcp documentation accurate because docs are part of the safety boundary.

## When to use

- Keeping README, GitHub Pages, safety docs, tool docs, changelog, or integration docs consistent with code
- Syncing docs after MCP tool surface changes, safety reclassifications, or release bumps
- Checking for stale tool counts, broken examples, or drifted installation instructions

## When not to use

- Changing MCP tool behavior — use `mcp-tool-safety-maintainer`
- Changing the review engine — use `review-runtime-maintainer`
- Semantic memory or vector store updates — use `semantic-memory-maintainer`
- Product positioning or README launch polish — use `repo-product-auditor`

## Docs Surfaces

Check the relevant docs in this order:

- `README.md`
- `docs/TOOL_SAFETY.md`
- `SAFETY_MODEL.md`
- `docs/security.md`
- `docs/install.md`
- `docs/clients.md`
- `docs/profiles.md`
- `docs/demo.md`
- `docs/integration.md`
- `TOOL_INDEX.md`
- `docs/semantic-index/mcp-tools-map.md`
- `docs/global/`
- `CHANGELOG.md`
- `ROADMAP.md`
- `docs/index.html`
- `docs/integration.html`

## Verify Claims Against Code

For command or tool claims, verify against:

- `mq-mcp/server.py`
- `mq-mcp/bridge.py`
- `scripts/validate.sh`
- `scripts/release-check.sh`
- `.github/workflows/`
- tests under `tests/`

## High-Risk Drift

Watch for:

- stale tool counts
- tools present in `server.py` but missing from safety docs
- docs listing tools that no longer exist
- README examples that require the wrong working directory
- install docs with wrong Python or `uv` instructions
- integration docs that mention `mq-hal` or `repo-signal` behavior not wired in `server.py`
- generated semantic docs that do not match the public tool surface

## Verification

```bash
./scripts/check-mcp-tool-docs.sh
./scripts/check-integration-docs.sh
./scripts/check-integration-smoke.sh
./scripts/check-bridge-tool-discovery.sh
./scripts/validate.sh
```

For docs-only edits, at minimum run the focused check that matches the edited surface.

## Editing Guidance

- Document only behavior that exists or is added in the same change.
- Prefer copy-pasteable commands with correct working directory.
- Keep safety language explicit and practical.
- Update `CHANGELOG.md` for user-facing behavior, tool surface changes, release behavior, safety policy changes, or docs that affect setup.
- Do not add promotional claims that the validation scripts cannot support.
