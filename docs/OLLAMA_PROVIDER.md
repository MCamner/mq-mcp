# mq-mcp Ollama Provider

Local model integration for learn extraction and review summarisation.

Last updated: 2026-06-07 (v1.12.0)

---

## Purpose

`mq-mcp/providers/ollama_provider.py` wraps the local Ollama HTTP API
(`http://localhost:11434`) with:

- JSON schema validation on every response
- Confidence and evidence field enforcement
- Hard exclusions (no release decisions, no destructive approvals)
- Graceful fallback when Ollama is unavailable

The provider is imported by `server.py` tools. It does not register MCP tools
itself — that boundary stays in `server.py`.

---

## Boundary

```text
Atlas One            — policy framing and prompt pack (ollama-runtime-policy)
mq-agent             — orchestration, run-tool gateway
server.py tools      — ollama_learn_status, ollama_learn_extract (Class B)
ollama_provider.py   — HTTP calls, schema validation, confidence enforcement
Ollama API           — local model runtime at localhost:11434
```

`MCamner/ollama` stays a clean upstream fork — no mq-specific files there.

---

## Public API

### `health() -> dict`

Returns Ollama availability and installed models. Never raises.

```python
{"status": "ok", "endpoint": "http://localhost:11434", "models": ["llama3.2", ...]}
{"status": "unavailable", "endpoint": "...", "error": "connection refused"}
```

### `list_models() -> list[str]`

Returns installed model names. Raises `OllamaUnavailableError` if Ollama is down.

### `chat_json(model, prompt, system, timeout) -> dict`

Sends a prompt, parses response as JSON. Raises `OllamaValidationError` if
response is not valid JSON.

### `extract_learn_items(findings, model, timeout) -> dict`

Extracts structured learn candidates from review findings text.

Returns:

```json
{
  "candidates": [...],   // valid items with should_store=true
  "rejected":  [...],    // failed validation or should_store=false
  "errors":    [...],    // parse/connection errors
  "model":     "...",
  "elapsed_ms": 1234
}
```

Each candidate conforms to `schemas/learn_extraction.schema.json`.
Low-confidence items (`confidence=low`) are auto-rejected.

### `review_summary(findings, source, model, timeout) -> dict`

Produces a `review_summary.v1` JSON object from review findings.
Conforms to `schemas/review_summary.schema.json`.

---

## Allowed Tasks

| Task | Tool | Provider method |
| ---- | ---- | --------------- |
| Learn extraction from review findings | `ollama_learn_extract` | `extract_learn_items()` |
| Review summarisation | _(future)_ | `review_summary()` |
| Model health check | `ollama_learn_status` | `health()` |

## Disallowed Tasks

The provider enforces these via system prompt and is never called for:

- Release go/no-go decisions
- Destructive command approval
- Secret or credential handling
- Direct memory writes (storage is always via `record_learning`)
- Bypassing mq-mcp safety class gates

---

## Configuration

| Env var | Default | Purpose |
| ------- | ------- | ------- |
| _(none)_ | `http://localhost:11434` | Base URL hardcoded; override planned for v1.13.0 |

Timeout defaults: 60s for chat, 3s for health checks.

---

## Schemas

| Schema | Purpose |
| ------ | ------- |
| `schemas/learn_extraction.schema.json` | Learn candidate items |
| `schemas/review_summary.schema.json` | Review session summary |
| `schemas/learning.schema.json` | Stored lesson record |

---

## Testing

```bash
# Check Ollama is running
mq-agent run-tool ollama_learn_status

# Extract learn candidates from last review
mq-agent run-tool ollama_learn_extract \
  --arg review_findings="$(cat /path/to/findings.txt)" \
  --approve
```

Unit tests: `tests/test_ollama_provider.py` (stub — to be filled when Ollama
is available in CI).
