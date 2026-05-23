# Changelog

## 0.2.2 - 2026-05-23

- Synced tool count to 19 across README, demo.md, and TOOL_SAFETY.md (README said "18", demo.md showed a stale 14-tool list).
- Fixed Python version requirement in docs/install.md from "3.14 or later" to ">=3.11".
- Updated demo.md tool list to include all 19 current MCP tools.
- Added Proof section to README.
- Added scripts/release-check.sh — pre-release gate covering shell syntax, Python compile, validate.sh, tests, version sync, and stale tool count detection.
- Added .github/workflows/docs-consistency.yml — CI checks for version sync, stale tool counts, and Python version accuracy in docs.
- Add bridge tool discovery smoke check for Bridget/MCP tool visibility.
- Add integration smoke check for mq-hal and repo-signal MCP tool wiring.
- Removed Bridget text face asset; Bridget face output now uses image assets only when available.

## 0.2.1 - 2026-05-18

- Added Bridget face identity asset.
- Added face trigger to `bridge.py` — prompts like "hur ser du ut", "visa dig", "who are you" show the face locally with zero API cost.
- Added Bridget face smoke-check to `scripts/validate.sh`.
- Synced `pyproject.toml` version to `0.2.1` and fixed description from placeholder.
- Added `resolve_allowed_local_file()` to `server.py` — `analyze_guitar_pro`, `open_in_app`, and `edit_image` now accept repo-relative or absolute paths, gated by `MQ_MCP_ALLOWED_PATHS`.
- Remaining 10 tools continue to use `resolve_repo_file()` — fully repo-scoped.
- Documented `MQ_MCP_ALLOWED_PATHS` in `mq-mcp/.env.example` and `docs/security.md`.
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
