# Learn extraction contract

This contract defines optional pattern extraction from mq-mcp review findings.

It is separate from the persistent learning record schema in
`schemas/learning.schema.json`. Extraction records are proposed intermediate
records. They must be validated and explicitly approved before any memory write.

The machine-readable extraction schema lives in
`schemas/learn_extraction.schema.json`. `mq-mcp/learn_engine.py`, tests, and
docs should use that file as the source of truth to avoid contract drift.

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
- empty `evidence`
- unsupported `pattern_type`
- unsupported `confidence`
- `should_store=true` without explicit caller approval
- `confidence=low` records from automatic storage

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
