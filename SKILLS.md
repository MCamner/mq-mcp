# Skills

mq-mcp ships local skills for maintaining the central cognition runtime, MCP
tool surface, semantic memory, learning engine, second brain, integration docs
and release readiness.

Note on namespaces: `skills/` holds agent skills (this index), while
`reviews/skills/` holds review-engine skills consumed by the review runtime.
They are unrelated surfaces that happen to share a name.

This file is generated from SKILL.md frontmatter by
`./scripts/check-skills.sh --fix`. Do not edit the table by hand.

## Built-in skills

| Skill | Description |
| ----- | ----------- |
| [brain-maintainer](skills/brain-maintainer/SKILL.md) | Use when changing the mqobsidian second brain, `brain_*` MCP tools, the Obsidian writer, vault schemas, or the knowledge contract. |
| [bridget-bridge-maintainer](skills/bridget-bridge-maintainer/SKILL.md) | Use when changing Bridget, bridge.py, OpenAI tool calling, MCP tool discovery, search modes, image behavior, or voice behavior. |
| [docs-maintainer](skills/docs-maintainer/SKILL.md) | Use when keeping mq-mcp README, GitHub Pages docs, installation guides, demo docs, safety docs, tool docs, changelog, roadmap, or semantic docs consistent with code. |
| [integration-stack-maintainer](skills/integration-stack-maintainer/SKILL.md) | Use when working on mq-mcp integrations with mq-hal, repo-signal, MQ_MCP_LOCAL_REPOS, semantic repo analysis, global docs, or cross-repo workflows. |
| [learn-engine-maintainer](skills/learn-engine-maintainer/SKILL.md) | Use when changing the mq-mcp learning engine, `learn_*` or `ollama_learn_*` tools, learning schemas, lesson storage, the Ollama provider, or learning contract docs. |
| [mcp-tool-safety-maintainer](skills/mcp-tool-safety-maintainer/SKILL.md) | Use when adding, changing, reviewing, or documenting mq-mcp FastMCP tools, path resolvers, write-capable tools, subprocess tools, or safety classifications. |
| [release-readiness](skills/release-readiness/SKILL.md) | Use when preparing mq-mcp for release by checking versioning, changelog, tool docs, safety docs, tests, validation scripts, generated docs, and Git state. |
| [repo-aware](skills/repo-aware/SKILL.md) | Use when inspecting, explaining, planning, reviewing, or changing mq-mcp with repository-specific context. |
| [review-runtime-maintainer](skills/review-runtime-maintainer/SKILL.md) | Use when changing mq-mcp review engine code, review contracts, review skills, severity parsing, multi-pass review, review memory, architecture memory, repo context selection, or review MCP tools. |
| [semantic-memory-maintainer](skills/semantic-memory-maintainer/SKILL.md) | Use when maintaining mq-mcp semantic memory packs, vector context, semantic index docs, global repo docs, or upload scripts. |
| [terminal-ui-polisher](skills/terminal-ui-polisher/SKILL.md) | Use when improving mq-mcp terminal output, Bridget CLI usage, validation scripts, release scripts, mqlaunch command surface, help screens, or status/error messages. |
