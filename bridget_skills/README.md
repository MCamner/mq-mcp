# Bridget skills

Recipes over tools Bridget already has. Bridget's system prompt carries only
each skill's name and description; she calls `load_skill` for the steps when a
request matches.

These are separate from `skills/`, which holds coding-agent skills that Claude
Code and Codex load automatically.

## Format

`bridget_skills/<name>/SKILL.md`:

```markdown
---
name: <name, same as the directory>
description: <one line: what it does and when to use it>
tools: <comma-separated MCP tools the steps call>
---

# Title

## Steg
1. ...
```

Values are unquoted `key: value` lines. Every tool in `tools:` must exist in
`mq-mcp/server.py` and appear in backticks in the body;
`tests/test_bridget_skills.py` checks both.

A skill grants no permissions. Tools that need approval still ask the operator.

## Skills from elsewhere

Set `MQ_MCP_SKILL_DIRS` to absolute directories separated by `:`. Skills from
there are marked `external` and treated as untrusted data. On a name clash, the
skill in this repo wins.
