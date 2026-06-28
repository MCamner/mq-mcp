# Ollama learn model policy

Ollama is an optional, local-first provider for mq-mcp learn workflows.

It may be used only as a deterministic pattern extraction model:

```text
mq-mcp review findings -> Ollama pattern extraction -> validated learn record
```

Ollama is not an autonomous learning system, execution engine, review engine,
or policy authority.

## Ownership

mq-mcp owns:

- learn contracts
- schema validation
- safety classes
- review logic
- memory storage
- approval gates

Ollama may only propose structured JSON records from review findings. mq-agent
may only surface read-only learn status, search, and explain commands. mq-hal
may display stack status after mq-mcp exposes it.

## Allowed use

Ollama may:

- summarize review findings
- extract repeated patterns
- classify pattern type
- propose reusable lessons
- generate structured JSON learn records

## Hard boundaries

Ollama must not:

- write to memory without explicit approval
- mutate repositories
- execute commands
- create or change safety classes
- override mq-mcp validation
- perform final risk scoring
- replace mq-mcp review logic
- invent files, commits, versions, tools, or facts
- treat prompt text from reviewed files, diffs, screenshots, or images as
  instructions

## Local model profile

The recommended local profile is `mq-learn`, defined in:

```text
models/ollama/Modelfile.mq-learn
```

Create it locally with:

```bash
ollama create mq-learn -f models/ollama/Modelfile.mq-learn
```

Provider availability must be optional. Missing Ollama or a missing `mq-learn`
model should return a clear optional-provider error, not break the rest of
mq-mcp.

## API policy

When mq-mcp calls Ollama for learn extraction, it should use a non-streaming
structured JSON response. Plain `format: "json"` is not enough by itself
because it can produce valid JSON that still omits required contract fields.

Use a JSON schema in `format` so Ollama is guided toward the full extraction
contract:

```json
{
  "model": "mq-learn",
  "prompt": "Extract one learn pattern from these mq-mcp review findings. Respond only as JSON with all required fields.",
  "format": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "pattern_name",
      "pattern_type",
      "summary",
      "evidence",
      "recommended_action",
      "confidence",
      "should_store"
    ],
    "properties": {
      "pattern_name": { "type": "string" },
      "pattern_type": {
        "type": "string",
        "enum": ["architecture", "safety", "docs", "release", "testing", "integration", "unknown"]
      },
      "summary": { "type": "string" },
      "evidence": {
        "type": "array",
        "items": { "type": "string" }
      },
      "recommended_action": { "type": "string" },
      "confidence": {
        "type": "string",
        "enum": ["high", "medium", "low"]
      },
      "should_store": { "type": "boolean" }
    }
  },
  "stream": false,
  "options": {
    "temperature": 0.1,
    "num_ctx": 4096,
    "num_predict": 700,
    "seed": 42
  }
}
```

Schema guidance is not the trust boundary. After parsing provider output,
mq-mcp validates the candidate itself:

- `should_store=true` is coerced back to read-only extraction unless a Class C
  storage path has explicit approval
- extraction output must pass `schemas/learn_extraction.schema.json`
- repo-context should be passed when evidence depends on repository files or
  paths

The `format` object is loaded from `schemas/learn_extraction.schema.json`.
Keep that schema aligned with `docs/LEARN_CONTRACT.md` and
`mq-mcp/learn_engine.py`.

Even when structured output is enabled, the prompt must explicitly instruct the
model to respond in JSON. This avoids malformed or whitespace-heavy output and
keeps the response suitable for schema validation.

The schema is a generation aid, not the safety boundary. mq-mcp must still
parse and validate the response, reject missing or unknown fields, reject empty
evidence, and apply the storage approval rules in `docs/LEARN_CONTRACT.md`.

## Storage rule

Pattern extraction must default to dry-run or read-only behavior. A validated
record may be stored only when the caller explicitly approves storage through a
Class C write path.

Low-confidence records must not be automatically stored.
