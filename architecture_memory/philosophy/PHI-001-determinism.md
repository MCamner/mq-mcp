---
id: PHI-001
title: Determinism over flexibility — same inputs, same output structure
date: 2026-05-28
status: stable
area: philosophy, architecture
---

## Invariant

Given the same inputs, a mq-mcp tool must always produce the same output
*structure* (though not necessarily the same AI-generated text). The output
shape — severity labels, field names, status codes, JSON schema — must be
predictable and machine-parseable without knowing what the model said.

This is a stronger guarantee than "consistent" — it means the parser for
tool output never needs to handle surprise formats.

## Rationale

Orchestrators and agents that consume mq-mcp tool output must be able to
parse it without inspecting the content. If output format varies by run,
agents need heuristics to interpret responses — and heuristics fail at the
worst moments. Deterministic output structure makes the runtime reliable
as infrastructure, not just as a helpful assistant.

## How to maintain

- Review contracts define output format. Changing a contract is a breaking change.
- `severity_engine.parse_findings()` is the canonical parser. If output must
  change format, the parser changes too — not just the prompt.
- New output fields must be additive, not structural replacements.
