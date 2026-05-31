# Learning Contract

`mq-mcp` learning is a deterministic, local-only memory layer for verified engineering lessons.

It is not an autonomous agent, self-training system, hidden daemon, or execution policy engine.

## Purpose

Learning records answer four questions:

1. What worked?
2. Why did it work?
3. How was it verified?
4. When should the pattern be reused?

The learning layer may improve review context, semantic memory, runbooks, and agent guidance. It must not weaken MCP runtime safety boundaries.

## Hard boundaries

Learning may:

- store verified engineering lessons
- summarize prior lessons
- support keyword search
- generate dry-run promotion previews for documentation
- provide context to future reviews or operator decisions

Learning must not:

- execute commands
- run subprocesses
- approve tool calls
- mutate router policy
- mutate safety classes
- mutate allowlists
- commit, push, merge, or tag
- store secrets
- store chain-of-thought
- upload memory without explicit user action
- write `AGENTS.md`, `CLAUDE.md`, or runbooks without explicit confirmation

## Safety classes

Read-only learning tools are Class A.

Write-capable learning tools are Class C because they write bounded local memory under:

```text
learn_engine/memory/lessons.jsonl
```

Promotion tools are Class C and must default to dry-run. They may produce a proposed text block for `docs/RUNBOOK.md`, `AGENTS.md`, `CLAUDE.md`, or architecture memory, but must not silently edit those files.

## Storage

The default store is repo-local JSONL:

```text
learn_engine/memory/lessons.jsonl
```

Each line is one record conforming to:

```text
schemas/learning.schema.json
```

The store is intentionally easy to inspect, back up, diff, and delete.

## Redaction

Before storage, learning input must be passed through secret redaction. At minimum, redact:

- OpenAI-style API keys
- `api_key`, `token`, `secret`, and `password` assignments
- bearer tokens

Redaction is a safety net, not a reason to paste secrets into learning records.

## Promotion

Promotion means turning a verified learning into guidance. Promotion is not execution.

Supported promotion targets:

- `docs/RUNBOOK.md`
- `AGENTS.md`
- `CLAUDE.md`
- `architecture_memory/`

Promotion must support dry-run preview and require explicit confirmation before writing.

## Non-goals

- no self-training
- no autonomous loops
- no hidden cloud sync
- no prompt-internal chain-of-thought capture
- no policy mutation based on learned content
- no command execution from learned content
