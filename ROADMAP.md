# Roadmap

This roadmap turns `mq-mcp` from a rough local experiment into a clear,
repeatable, and publishable MCP project for macOS.

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

## v0.2.3 — AI tooling integration

Goal: wire in mq-image-analyze and Claude Code subagents for richer local intelligence.

- [x] Bridget face lines dynamically generated via `mq-image-analyze`
- [x] Parallel mq-image analysis with chafa rendering — lower latency
- [x] Fix Bridget face output routing to `/dev/tty` (survives piped contexts)
- [x] Add Claude Code subagents: `mq-project-context`,
  `mcp-tool-safety-reviewer`, `mcp-release-validator`
- [ ] Bump VERSION to 0.2.3
- [ ] Update CHANGELOG

## v0.3.0 — Usable macOS MCP toolkit

Status: done.

- [x] Add a stable launcher command
- [x] Add documented MCP server profiles
- [x] Add setup examples for common MCP clients
- [x] Add screenshots for installation and usage
- [x] Add a complete troubleshooting page
- [x] Add example workflows
- [x] Add clear upgrade instructions

## v0.4.0 — Stable local AI platform

Goal: make mq-mcp a solid foundation for local AI-assisted workflows.

- [ ] Full release of v0.2.3 (version bump, CHANGELOG, tag)
- [ ] Expand Claude Code subagent coverage (discovery, safety, integration)
- [ ] Expose mq-image-analyze as a first-class MCP tool
- [ ] Add Bridget session context (state across bridge prompts)
- [ ] Document the mq-* ecosystem (mq-mcp, mq-agent, mq-image, repo-signal)
- [ ] Add a release-readiness checklist to `scripts/release-check.sh`

## Later

- [ ] Integrate with `mqlaunch` for one-command MCP stack startup
- [ ] Add a polished terminal menu for tool selection
- [ ] Add MCP profile templates (minimal, full, secure)
- [ ] Add repo-signal MCP tools for cross-repo architecture queries
- [ ] Add docs for secure local automation patterns
- [ ] Add packaged install flow (Homebrew or standalone)
- [ ] Add demo videos or GIFs for README and GitHub Pages
- [ ] Publish a stable v1.0 once setup, validation, docs, and safety are solid
