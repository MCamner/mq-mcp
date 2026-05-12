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

- [ ] Fix root README formatting
- [ ] Explain what the project is and is not
- [ ] Document the repository layout
- [ ] Document the local setup flow
- [ ] Document how to run the MCP server
- [ ] Document how to run the OpenAI/MCP bridge
- [ ] Add clear safety notes
- [ ] Add basic development checks
- [ ] Confirm GitHub Pages link works
- [ ] Add at least one screenshot or terminal output example

## v0.1.2 — Local validation flow

Goal: make it easy to verify that the local MCP setup works.

- [ ] Add a simple validation command
- [ ] Add expected output examples
- [ ] Add troubleshooting notes for missing `uv`
- [ ] Add troubleshooting notes for Python version mismatch
- [ ] Add troubleshooting notes for missing OpenAI credentials
- [ ] Add troubleshooting notes for MCP server startup failures
- [ ] Add a small smoke-test script
- [ ] Add a release-readiness checklist

## v0.2.0 — Safer MCP server structure

Goal: make the local MCP server safer and easier to extend.

- [ ] Replace hardcoded local paths with config or environment variables
- [ ] Add an explicit filesystem allowlist
- [ ] Document every exposed MCP tool
- [ ] Separate system tools from repo/file tools
- [ ] Add safer error handling
- [ ] Add tests for path safety
- [ ] Add tests for tool output shape
- [ ] Add a minimal example config file

## v0.2.1 — GitHub Actions and quality checks

Goal: avoid regressions and make the repo visibly healthy.

- [ ] Add Python syntax check workflow
- [ ] Add basic test workflow
- [ ] Add README/link validation
- [ ] Add secret scanning guidance
- [ ] Add status badge when CI exists
- [ ] Add release checklist to docs

## v0.3.0 — Usable macOS MCP toolkit

Goal: make the repo useful beyond a one-off experiment.

- [ ] Add a stable launcher command
- [ ] Add documented MCP server profiles
- [ ] Add setup examples for common MCP clients
- [ ] Add screenshots for installation and usage
- [ ] Add a complete troubleshooting page
- [ ] Add example workflows
- [ ] Add clear upgrade instructions

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
