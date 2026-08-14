# Learn extraction contract

This contract defines optional pattern extraction from mq-mcp review findings.

It is separate from the persistent learning record schema in
`schemas/learning.schema.json`. Extraction records are proposed intermediate
records. They must be validated and explicitly approved before any memory write.

The machine-readable extraction schema lives in
`schemas/learn_extraction.schema.json`. `mq-mcp/learn_engine.py`, tests, and
docs should use that file as the source of truth to avoid contract drift.

## Public MCP surface

The MCP tools are the authoritative public surface for learn extraction and
storage. mq-mcp does not provide a separate `mq-mcp learn ...` CLI.

- `ollama_learn_status` (Class B) checks the optional local provider.
- `ollama_learn_extract` (Class B) extracts a dry-run candidate from supplied
  review findings.
- `learn_extract_from_last_review` (Class B) extracts a dry-run candidate from
  stored review findings.
- `learn_from_review` (Class C) stores a learning from the latest review.
- `learn_from_diff` (Class C) stores an explicitly supplied learning with the
  current diff summary as validation context.

Extraction tools never write. Storage remains in separate Class C tools; the
caller must choose those tools explicitly.

## Repository context and provenance

Repository-specific extraction requires a verified repo context. mq-mcp reads
`.repo-signal/exports/symbol_index.json` and accepts it only when:

- `schema` is `symbol_index.v1`
- `repo_name` matches the requested repository
- `generated_at` is timezone-aware, no more than 24 hours old, and no more
  than five minutes in the future
- every included path resolves to an existing file inside that repository

The context sent to Ollama includes those provenance fields. If the artifact is
missing, malformed, belongs to another repository, or contains no verifiable
files, mq-mcp returns an `unknown` / `low` refusal with empty evidence without
calling the model. The learning layer reads exports but does not execute
repo-signal or git.

Successful and refused MCP previews expose context status, source, and export
timestamp so callers can distinguish grounded output from a missing/stale
context refusal.

There is intentionally no git subprocess fallback in the learning layer. Such
a fallback would violate its non-executing boundary and change the Class B MCP
subprocess contract. Operators should refresh the repo-signal export; refusal
is the safe behavior while it is unavailable or stale.

## Input

The input is mq-mcp review findings, such as output from:

- `review_file`
- `review_diff`
- `review_repo`
- `risk_review_file`
- `risk_review_diff`

Inputs must be treated as data. Instructions, prompts, shell commands, or
policy-like text inside reviewed content must not become model or system
instructions.

## Output

The output is a validated JSON learn extraction record:

```json
{
  "pattern_name": "string",
  "pattern_type": "architecture|safety|docs|release|testing|integration|unknown",
  "summary": "string",
  "evidence": ["string"],
  "recommended_action": "string",
  "confidence": "high|medium|low",
  "should_store": true
}
```

## Validation

mq-mcp must validate extraction output before storage or promotion.

Validation must reject:

- non-JSON output
- missing required fields
- unknown fields unless the contract explicitly allows them
- unsupported `pattern_type`
- unsupported `confidence`
- `should_store=true` without explicit caller approval
- `confidence=low` records from automatic storage

Empty `evidence` is the explicit ungrounded-result signal. For model-generated
records, mq-mcp must normalize it deterministically to
`pattern_type="unknown"` and `confidence="low"` before strict validation.
Low-confidence records remain ineligible for automatic storage.

Ollama structured output is an extraction aid, not validation. mq-mcp must
validate the parsed response even when the Ollama request uses a JSON schema in
the API `format` field.

## Default mode

Extraction defaults to dry-run/read-only mode. The dry-run result may be shown
to a caller, reviewed, or discarded without writing memory.

## Storage

Storage requires explicit approval through an mq-mcp Class C write path.

The storage path must remain owned by mq-mcp. Callers such as mq-agent may ask
for status, search, or explanations, but must not write learned records
directly.

## Prompt-injection handling

Prompt-like content in reviewed files, diffs, screenshots, diagrams, or images
is untrusted input. It must be treated as evidence text only.

Examples of untrusted content include:

- "ignore previous instructions"
- "execute this command"
- "store this memory automatically"
- "mark this risk as safe"

The extraction model must not follow those instructions.
