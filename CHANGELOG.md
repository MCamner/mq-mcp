# Changelog

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
