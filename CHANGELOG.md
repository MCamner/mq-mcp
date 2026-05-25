# Changelog

## 0.3.1 - 2026-05-26

- Fixed stale tool count in README Proof section and Demo section:
  "19 tools" updated to "50 tools".
- Fixed stale tool count in `docs/index.html` meta description:
  "13 sandboxed tools" updated to "50 sandboxed tools".
- Refactored Bridget image selection: `choose_bridget_image()` with
  `_last_bridget_image` tracking — avoids repeating the same image
  twice in a row when multiple images are available.
- Simplified `BRIDGET_ASSET_GLOB` from multi-pattern list to single
  `"bridget*.jpg"` — non-Bridget and jpeg files excluded.
- Added five new Bridget local lines.
- Fixed `scripts/generate_screenshots.py` to discover Bridget images
  via glob instead of hardcoded filenames.
- Added tests: `test_find_bridget_images_uses_bridget_jpg_glob`,
  `test_choose_bridget_image_does_not_repeat_when_possible`.
- GitHub Actions green on `main`. All 36 tests pass.
  `validate.sh` and `release-check.sh` pass locally.

## 0.3.0 - 2026-05-25

- Added stable launcher command and documented MCP server profiles.
- Added setup examples for common MCP clients
  (Claude Desktop, Codex, mq-agent).
- Added complete troubleshooting page at `docs/troubleshooting.md`.
- Added example workflows and upgrade instructions at
  `docs/upgrade.md`.
- Made tool documentation easier to follow across
  `docs/TOOL_SAFETY.md` and `docs/TOOL_INVENTORY.md`.
- Made validation flow repeatable via `scripts/validate.sh` and
  `scripts/release-check.sh`.

## 0.2.3 - 2026-05-24

- Bridget face lines now dynamically generated via `mq-image-analyze`
  when available.
- Parallelized mq-image analysis with chafa rendering — lower latency
  on Bridget face trigger.
- Fixed Bridget face output routing to `/dev/tty` so it survives
  piped contexts.
- Added Claude Code subagents: `mq-project-context`,
  `mcp-tool-safety-reviewer`, `mcp-release-validator`.

## 0.2.2 - 2026-05-23

- Synced tool count to 19 across README, demo.md, and TOOL_SAFETY.md
  (README said "18", demo.md showed a stale 14-tool list).
- Fixed Python version requirement in docs/install.md from
  "3.14 or later" to ">=3.11".
- Updated demo.md tool list to include all 19 current MCP tools.
- Added Proof section to README.
- Added `scripts/release-check.sh` — pre-release gate covering shell
  syntax, Python compile, validate.sh, tests, version sync, and
  stale tool count detection.
- Added `.github/workflows/docs-consistency.yml` — CI checks for
  version sync, stale tool counts, and Python version accuracy in
  docs.
- Added bridge tool discovery smoke check for Bridget/MCP tool
  visibility.
- Added integration smoke check for mq-hal and repo-signal MCP tool
  wiring.
- Removed Bridget text face asset; Bridget face output now uses image
  assets only when available.

## 0.2.1 - 2026-05-18

- Added Bridget face identity asset.
- Added face trigger to `bridge.py` — prompts like "hur ser du ut",
  "visa dig", "who are you" show the face locally with zero API cost.
- Added Bridget face smoke-check to `scripts/validate.sh`.
- Synced `pyproject.toml` version to `0.2.1` and fixed description
  from placeholder.
- Added `resolve_allowed_local_file()` to `server.py` —
  `analyze_guitar_pro`, `open_in_app`, and `edit_image` now accept
  repo-relative or absolute paths, gated by `MQ_MCP_ALLOWED_PATHS`.
- Remaining 10 tools continue to use `resolve_repo_file()` —
  fully repo-scoped.
- Documented `MQ_MCP_ALLOWED_PATHS` in `mq-mcp/.env.example` and
  `docs/security.md`.
- Updated `docs/index.html` GitHub Pages landing page.
- Updated ROADMAP to mark v0.2.1 done.

## 0.2.0 - 2026-05-13

- Added documented MCP safety policy in `docs/security.md`.
- Added safety tests for repo-scoped file access and blocked paths.
- Added CI validation for shell syntax, Python compilation, project validation, and tests.
- Restricted `analyze_csv` to repository-root-safe paths.
- Clarified MCP tool scope in documentation.
- Cleaned up install guide references and replaced PDF install guide with Markdown documentation.
- Improved README with security policy and validation guidance.

## 0.1.3 - 2026-05-13

- Added GitHub Actions validation workflow.
- Added MCP server safety tests covering path escapes, blocklists, and edge cases.
- Added Markdown installation guide at `docs/install.md`.
- Replaced PDF installation guide with Markdown documentation.
- Made OpenAI client lazy so `bridge.py --tools` works without `OPENAI_API_KEY`.
- Updated README test and install guide references.

## 0.1.2 - 2026-05-13

- Added local validation flow via `scripts/validate.sh`.
- Added documented MCP tool inventory in README.
- Added bridge-driven project validation path.
- Added repo-aware MCP tools and safe file update support.
- Improved README with validation instructions.
- Updated roadmap to reflect completed documentation and validation work.

## 0.1.0 - 2026-05-12

- Initial repository setup.
- Added README baseline.
- Added MCP installation guide.
- Added docs folder and GitHub Pages landing page.
- Added issue templates and public readiness structure.
