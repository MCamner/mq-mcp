---
id: ADR-005
title: API keys and secrets never appear in tool output
date: 2026-05-28
status: accepted
area: safety, server, observability
---

## Decision

No MCP tool output, log line, diagnostic report, or error message may contain
API keys, tokens, passwords, or local filesystem paths that could identify the
user's machine. `_redacted_env()` must be used for all diagnostic output that
touches environment variables.

## Rationale

MCP tool output is forwarded to orchestrators, agents, and LLM context windows.
A secret that leaks into a tool response propagates to model context, logs, and
potentially to remote API providers. The blast radius of a single leaked
OPENAI_API_KEY is an account compromise.

## Consequences

- `_redacted_env()` masks any env var whose name contains KEY, TOKEN, SECRET,
  PASSWORD, or similar patterns.
- `mq-mcp report --json` and `mq-mcp bundle` use `_redacted_env()` exclusively.
- Tests assert that injecting a fake API key into the environment does not cause
  it to appear in diagnostic output.
- Any new tool that reads env vars must redact before including values in output.
