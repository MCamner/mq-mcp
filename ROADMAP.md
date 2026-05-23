# Roadmap

This roadmap turns `mq-mcp` from a rough local experiment into a clear, repeatable, and publishable MCP project for macOS.

## v0.1.0 — Public baseline

Status: done.

- [x] Create repository
- [x] Add README
- [x] Add LICENSE
- [x] Add CHANGELOG
- [x] Add VERSION
- [x] Add ROADMAP
- [x] Add GitHub Pages docs folder
- [x] Add `docs/index.html`
- [x] Add `docs/screenshots/`
- [x] Add issue templates
- [x] Add first release

## v0.1.1 — Documentation cleanup

Goal: make the project understandable from the GitHub front page.

- [x] Fix root README formatting
- [x] Explain what the project is and is not
- [x] Document the repository layout
- [x] Document the local setup flow
- [x] Document how to run the MCP server
- [x] Document how to run the OpenAI/MCP bridge
- [x] Add clear safety notes
- [x] Add basic development checks
- [x] Confirm GitHub Pages link works
- [x] Add at least one screenshot or terminal output example

## v0.1.2 — Local validation flow

Goal: make it easy to verify that the local MCP setup works.

- [x] Add a simple validation command
- [x] Add expected output examples
- [x] Add troubleshooting notes for missing `uv`
- [x] Add troubleshooting notes for Python version mismatch
- [x] Add troubleshooting notes for missing OpenAI credentials
- [x] Add troubleshooting notes for MCP server startup failures
- [x] Add a small smoke-test script
- [ ] Add a release-readiness checklist

## v0.2.0 — Safer MCP server structure

Goal: make the local MCP server safer and easier to extend.

- [x] Replace hardcoded local paths with config or environment variables
- [x] Add an explicit filesystem allowlist
- [x] Document every exposed MCP tool
- [x] Separate system tools from repo/file tools
- [x] Add safer error handling
- [x] Add tests for path safety
- [x] Add tests for tool output shape
- [x] Add a minimal example config file

## v0.2.1 — Bridget identity + repo metadata sync

Status: done.

- [x] Add Python syntax check workflow
- [x] Add basic test workflow
- [x] Add status badge when CI exists
- [x] Add Bridget face identity asset
- [x] Add Bridget face trigger to `bridge.py` (zero API cost, local)
- [x] Add Bridget smoke-check to `scripts/validate.sh`
- [x] Sync `pyproject.toml` version with `VERSION`
- [x] Migrate all remaining unsafe `os.path.normpath` paths in `server.py` to `resolve_repo_file()`
- [x] Update `docs/index.html` GitHub Pages landing

## v0.2.2 — Credibility polish

Status: done.

- [x] Sync tool count to 19 across README, demo.md, and TOOL_SAFETY.md
- [x] Fix Python version requirement in docs/install.md (3.14 → >=3.11)
- [x] Update demo.md tool list from 14 stale tools to all 19 current tools
- [x] Add Proof section to README
- [x] Add scripts/release-check.sh
- [x] Add .github/workflows/docs-consistency.yml

## v0.3.0 — Usable macOS MCP toolkit

Goal: make the repo useful beyond a one-off experiment.

- [x] Add a stable launcher command
- [x] Add documented MCP server profiles
- [x] Add setup examples for common MCP clients
- [x] Add screenshots for installation and usage
- [x] Add a complete troubleshooting page
- [x] Add example workflows
- [x] Add clear upgrade instructions

## Later

Ideas for later versions:

- [ ] Integrate with `mqlaunch`
- [ ] Add a polished terminal menu
- [ ] Add MCP profile templates
- [ ] Add repo-aware MCP tools
- [ ] Add docs for secure local automation
- [ ] Add packaged install flow
- [ ] Add demo videos or GIFs
- [ ] Publish a stable v1.0 release once setup, validation, docs, and safety boundaries are solid
