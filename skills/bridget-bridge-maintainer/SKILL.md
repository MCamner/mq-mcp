---
name: bridget-bridge-maintainer
description: Use when changing Bridget, bridge.py, OpenAI tool calling, MCP tool discovery, search modes, the --chat REPL, the multi-round tool loop, session persistence, image behavior, or voice behavior.
---

# Bridget Bridge Maintainer

Use this skill for `mq-mcp/bridge.py`, Bridget behavior, OpenAI tool
calls, and the local MCP bridge experience.

## When to use

* Changing `bridge.py`, Bridget behavior, OpenAI tool calling schema, or MCP tool discovery
* Debugging bridge startup, tool discovery, or `content_to_text()` conversion
* Modifying `--tools`, `--search`, or `--search-global` behavior
* Changing the `--chat` REPL, the multi-round tool loop (`run_turn`,
  `MAX_TOOL_ROUNDS`), context trimming, or REPL session persistence
* Changing Bridget voice or image response behavior

## When not to use

* Adding new MCP tools to `server.py` — use `mcp-tool-safety-maintainer`
* Fixing CLI output unrelated to bridge mode — use `terminal-ui-polisher`
* Review engine changes — use `review-runtime-maintainer`

## Evals

### Should trigger

* "bridge.py --tools crashes on startup"
* "Bridget answers with tools that don't exist"
* "convert the new MCP tool schema to OpenAI format"
* "make Bridget's voice output optional"

### Should not trigger

* "add a new MCP tool to server.py" → use `mcp-tool-safety-maintainer`
* "clean up validate.sh output" → use `terminal-ui-polisher`
* "fix severity parsing" → use `review-runtime-maintainer`
* "update the README demo section" → use `docs-maintainer`

## Core Files

* `mq-mcp/bridge.py`
* `mq-mcp/ask.py`
* `mq-mcp/bridget_voice.py`
* `mq-mcp/bridget_context.py`
* `mq-mcp/bridget_runtime.py`
* `mq-mcp/server.py`
* `docs/bridget-voice.md`
* `docs/demo.md`
* `README.md`
* `tests/test_bridget_images.py`
* `tests/test_bridget_voice.py`
* `tests/test_bridge_refactor.py`
* `tests/test_bridget_context.py`
* `tests/test_bridget_runtime.py`
* `scripts/check-bridge-tool-discovery.sh`

## Key Behavior

The bridge:

* starts the MCP server through `SERVER_COMMAND` and `SERVER_ARGS`
* discovers actual MCP tools before answering
* converts MCP tool schemas into OpenAI tool definitions
* handles `--tools`, `--search`, and `--search-global`
* runs a bounded multi-round tool loop in `run_turn` (`MAX_TOOL_ROUNDS`), passing
  `tools=` on every model call so DO MODE can chain tool calls
* offers an interactive REPL via `--chat` (one session + system message alive,
  context trimmed for long sessions, recorded once at exit — not per turn)
* prints tool calls for visibility
* supports Bridget image responses and optional local macOS speech

## Guardrails

* Do not invent tools in the prompt or output.
* Tool answers must come from the discovered MCP catalog.
* Keep `--tools` working without requiring `OPENAI_API_KEY`.
* Keep errors concise when the MCP server or a tool call fails.
* Preserve local-only voice behavior.
* Do not add external TTS unless explicitly requested and documented.
* Avoid hardcoding model names or paths when env vars already exist.
* Do not break scriptability with animations or noisy machine-mode output.

## When Changing Tool Calling

Check:

* MCP content conversion in `content_to_text()`
* OpenAI tool schema conversion in `to_openai_tools()`
* argument parsing in `call_mcp_tool()`
* model/env defaults
* subprocess server startup command
* handling of malformed JSON tool arguments

## Verification

```bash
python -m compileall mq-mcp/bridge.py mq-mcp/ask.py mq-mcp/bridget_voice.py \
  mq-mcp/bridget_context.py mq-mcp/bridget_runtime.py -q
uv --directory mq-mcp run python bridge.py --tools
./scripts/check-bridge-tool-discovery.sh
uv --directory mq-mcp run pytest \
  ../tests/test_bridget_images.py \
  ../tests/test_bridget_voice.py \
  ../tests/test_bridge_refactor.py \
  ../tests/test_bridget_context.py \
  ../tests/test_bridget_runtime.py \
  -q
```

If `OPENAI_API_KEY` is available and the task touched the REPL, smoke it:

```bash
uv --directory mq-mcp run python bridge.py --chat <<< 'exit'   # must greet and exit 0
```

If `OPENAI_API_KEY` is available and the task touched prompt flow:

```bash
uv --directory mq-mcp run python bridge.py "List the available MCP tools."
```

## UX Standard

Bridget should feel local, fast, practical, and transparent.
Preserve personality where it exists, but keep operational output calm
and debuggable.
