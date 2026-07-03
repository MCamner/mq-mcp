"""Regression tests for the Phase 0 bridge.py execution refactor.

These lock the behavior of the functions extracted from run_bridge
(discover_tools, build_system_content, execute_tool_calls, run_turn,
print_response) so the Phase 1 multi-round loop can be added without silently
changing existing one-shot behavior.
"""

import asyncio
import importlib.util
import io
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "mq-mcp" / "bridge.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))


@pytest.fixture()
def bridge():
    sys.modules.setdefault(
        "mcp",
        types.SimpleNamespace(ClientSession=object, StdioServerParameters=object),
    )
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_refactor", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- Fakes for the OpenAI client and MCP session -------------------------------


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)

    def model_dump(self, exclude_none=True):
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


class _FakeMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


def _response(message):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(responses))


class _FakeSession:
    """Records tool calls; returns MCP-style content objects with a .text attr."""

    def __init__(self, result_text="ok", tools=None):
        self._result_text = result_text
        self._tools = tools or []
        self.tool_calls = []

    async def list_tools(self):
        return types.SimpleNamespace(tools=self._tools)

    async def call_tool(self, name, args):
        self.tool_calls.append((name, args))
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(text=self._result_text)]
        )


# --- discover_tools ------------------------------------------------------------


def test_discover_tools_returns_catalog_and_openai_specs(bridge):
    tool = types.SimpleNamespace(
        name="git_status",
        description="Show status",
        inputSchema={"type": "object", "properties": {}},
    )
    session = _FakeSession(tools=[tool])

    catalog, openai_tools = asyncio.run(bridge.discover_tools(session))

    assert "git_status" in catalog
    assert openai_tools[0]["function"]["name"] == "git_status"


# --- build_system_content ------------------------------------------------------


def _fake_ctx(session="", lessons=""):
    return types.SimpleNamespace(load=lambda: session, load_lessons=lambda: lessons)


def test_build_system_content_includes_prompt_context_and_catalog(bridge, monkeypatch):
    monkeypatch.setattr(
        bridge.bridget_runtime, "project_context_block", lambda: "\n\n## PROJECT"
    )
    ctx = _fake_ctx(session="\n\n## SESSION", lessons="\n\n## LESSONS")

    content = bridge.build_system_content(ctx, "Available MCP tools:\n- git_status", do_mode=False)

    assert "mq-mcp" in content  # from SYSTEM_PROMPT
    assert "## SESSION" in content
    assert "## LESSONS" in content
    assert "## PROJECT" in content
    assert "Available MCP tools:" in content
    assert "DO MODE" not in content


def test_build_system_content_adds_do_block_only_in_do_mode(bridge, monkeypatch):
    monkeypatch.setattr(bridge.bridget_runtime, "project_context_block", lambda: "")
    ctx = _fake_ctx()

    content = bridge.build_system_content(ctx, "catalog", do_mode=True)

    assert "DO MODE (ACTIVE)" in content
    assert "shell_exec is ENABLED" in content


# --- run_turn ------------------------------------------------------------------


def test_run_turn_direct_answer_no_tools(bridge):
    client = _FakeClient([_response(_FakeMessage("hello world", None))])
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]

    answer, called, did_tool_round = asyncio.run(
        bridge.run_turn(
            client=client,
            model="m",
            messages=messages,
            openai_tools=[],
            do_mode=False,
            session=_FakeSession(),
        )
    )

    assert answer == "hello world"
    assert called == []
    assert did_tool_round is False
    # Exactly one model call, tools offered, tool_choice auto (not forced).
    assert len(client.chat.completions.calls) == 1
    assert client.chat.completions.calls[0]["tool_choice"] == "auto"
    assert "tools" in client.chat.completions.calls[0]


def test_run_turn_single_tool_round_do_mode(bridge):
    tool_call = _FakeToolCall("call_1", "git_status", '{"repo": "."}')
    first = _response(_FakeMessage("", [tool_call]))
    final = _response(_FakeMessage("done summarizing", None))
    client = _FakeClient([first, final])
    session = _FakeSession(result_text="clean tree")
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "status?"}]

    answer, called, did_tool_round = asyncio.run(
        bridge.run_turn(
            client=client,
            model="m",
            messages=messages,
            openai_tools=[{"type": "function", "function": {"name": "git_status"}}],
            do_mode=True,
            session=session,
        )
    )

    assert answer == "done summarizing"
    assert called == ["git_status"]
    assert did_tool_round is True
    # The tool was actually invoked with parsed args.
    assert session.tool_calls == [("git_status", {"repo": "."})]
    # First call forces a tool in --do mode; the final call omits tools.
    assert client.chat.completions.calls[0]["tool_choice"] == "required"
    assert "tools" not in client.chat.completions.calls[1]
    # History carries the assistant tool_calls turn and the tool result.
    assert any(
        m.get("role") == "tool" and m.get("content") == "clean tree" for m in messages
    )


# --- print_response ------------------------------------------------------------


def test_print_response_plain_prefix(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "speak_if_enabled", lambda *_a, **_k: None)
    buf = io.StringIO()  # no isatty -> scramble_print writes plain text
    monkeypatch.setattr(bridge.sys, "stdout", buf)

    bridge.print_response("answer text", prefix_newline=False)

    assert buf.getvalue() == "Bridget: answer text\n"


def test_print_response_newline_prefix(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "speak_if_enabled", lambda *_a, **_k: None)
    buf = io.StringIO()
    monkeypatch.setattr(bridge.sys, "stdout", buf)

    bridge.print_response("x", prefix_newline=True)

    assert buf.getvalue() == "\nBridget: x\n"
