# mq-mcp Vector Context

Project: mq-mcp

Purpose:
mq-mcp is a local-first MCP server experiment and tooling lab for macOS.

Main goals:
- make MCP setup easier to understand
- provide local MCP tools
- validate project safety and structure
- document repeatable setup and troubleshooting flows
- support repo-aware local automation experiments

Important files:
- mq-mcp/server.py: local FastMCP server and MCP tool definitions
- mq-mcp/bridge.py: bridge between OpenAI and local MCP server
- scripts/validate.sh: local validation script
- docs/security.md: MCP safety policy
- docs/install.md: macOS installation guide
- docs/demo.md: example commands and expected output
- README.md: public front door
- ROADMAP.md: planned work
- CHANGELOG.md: release history

Project status:
Early prototype. Useful for local experimentation, documentation, and validation. Not production-ready.
