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
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "mq-mcp" / "bridge.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))


@pytest.fixture()
def bridge():
    # Stub the mcp package so bridge.py imports without the real dependency.
    # Typed Any because these are dynamic module stubs, not real modules.
    mcp_stub: Any = types.ModuleType("mcp")
    mcp_stub.ClientSession = object
    mcp_stub.StdioServerParameters = object
    sys.modules.setdefault("mcp", mcp_stub)
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio: Any = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_refactor", BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
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
    # --do mode forces a tool on the first round; every later call uses
    # tool_choice=auto but still offers tools (Phase 1: chained calls possible).
    assert client.chat.completions.calls[0]["tool_choice"] == "required"
    assert client.chat.completions.calls[1]["tool_choice"] == "auto"
    assert "tools" in client.chat.completions.calls[1]
    # History carries the assistant tool_calls turn and the tool result.
    assert any(
        m.get("role") == "tool" and m.get("content") == "clean tree" for m in messages
    )


def test_run_turn_chains_multiple_tool_rounds(bridge):
    round1 = _response(_FakeMessage("", [_FakeToolCall("c1", "alpha", "{}")]))
    round2 = _response(_FakeMessage("", [_FakeToolCall("c2", "beta", "{}")]))
    final = _response(_FakeMessage("all done", None))
    client = _FakeClient([round1, round2, final])
    session = _FakeSession(result_text="step ok")
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]

    answer, called, did_tool_round = asyncio.run(
        bridge.run_turn(
            client=client,
            model="m",
            messages=messages,
            openai_tools=[{"type": "function", "function": {"name": "alpha"}}],
            do_mode=True,
            session=session,
        )
    )

    assert answer == "all done"
    # Tools accumulate across every round, in order.
    assert called == ["alpha", "beta"]
    assert did_tool_round is True
    assert [name for name, _ in session.tool_calls] == ["alpha", "beta"]
    # Three model calls: required, then auto, then auto — all offering tools.
    choices = [c["tool_choice"] for c in client.chat.completions.calls]
    assert choices == ["required", "auto", "auto"]
    assert all("tools" in c for c in client.chat.completions.calls)


def test_run_turn_stops_at_max_rounds(bridge):
    # A model that never stops calling tools must not loop forever.
    responses = [
        _response(_FakeMessage("", [_FakeToolCall(f"c{i}", "loop_tool", "{}")]))
        for i in range(bridge.MAX_TOOL_ROUNDS)
    ]
    client = _FakeClient(responses)
    session = _FakeSession()
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "spin"}]

    answer, called, did_tool_round = asyncio.run(
        bridge.run_turn(
            client=client,
            model="m",
            messages=messages,
            openai_tools=[{"type": "function", "function": {"name": "loop_tool"}}],
            do_mode=False,
            session=session,
        )
    )

    assert "MAX_TOOL_ROUNDS" in answer
    assert did_tool_round is True
    assert len(called) == bridge.MAX_TOOL_ROUNDS
    assert len(session.tool_calls) == bridge.MAX_TOOL_ROUNDS
    # Exactly MAX_TOOL_ROUNDS model calls, no more.
    assert len(client.chat.completions.calls) == bridge.MAX_TOOL_ROUNDS


# --- parse_prompt: --chat flag -------------------------------------------------


def test_parse_prompt_chat_flag_no_initial_prompt(bridge, monkeypatch):
    monkeypatch.setattr(bridge.sys, "argv", ["bridge.py", "--chat"])

    prompt, list_tools_only, do_mode, model, search, search_global, chat_mode = (
        bridge.parse_prompt()
    )

    assert chat_mode is True
    assert prompt == ""  # initial prompt optional under --chat
    assert list_tools_only is False
    assert do_mode is False


def test_parse_prompt_chat_flag_with_initial_prompt(bridge, monkeypatch):
    monkeypatch.setattr(bridge.sys, "argv", ["bridge.py", "--chat", "vilka", "verktyg"])

    prompt, *_rest, chat_mode = bridge.parse_prompt()

    assert chat_mode is True
    assert prompt == "vilka verktyg"


def test_parse_prompt_oneshot_sets_chat_false(bridge, monkeypatch):
    monkeypatch.setattr(bridge.sys, "argv", ["bridge.py", "list", "tools"])

    prompt, list_tools_only, do_mode, model, search, search_global, chat_mode = (
        bridge.parse_prompt()
    )

    assert prompt == "list tools"
    assert chat_mode is False
    assert do_mode is False


# --- REPL stdin handling -------------------------------------------------------


class _BrokenStdin:
    def readline(self):
        raise UnicodeDecodeError("utf-8", b"\xc3", 0, 1, "invalid continuation byte")


def test_read_chat_stdin_line_handles_bad_utf8(bridge, monkeypatch):
    monkeypatch.setattr(bridge.sys, "stdin", _BrokenStdin())
    out = io.StringIO()

    line = bridge.read_chat_stdin_line(out)

    assert line == ""
    assert "ogiltig UTF-8" in out.getvalue()


def test_read_chat_stdin_line_returns_none_on_eof(bridge, monkeypatch):
    monkeypatch.setattr(bridge.sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(bridge, "bridget_goodbye_message", lambda: "Hej då.")
    out = io.StringIO()

    line = bridge.read_chat_stdin_line(out)

    assert line is None
    assert "Hej då." in out.getvalue()


# --- Phase 4: record_chat_session ----------------------------------------------


class _RecordingCtx:
    """Captures the single record() call a REPL session makes at exit."""

    def __init__(self):
        self.calls = []

    def record(self, prompt, tools, answer, **kwargs):
        self.calls.append((prompt, tools, answer, kwargs))


def test_record_chat_session_records_once_with_metadata(bridge, monkeypatch):
    monkeypatch.setattr(
        bridge.bridget_runtime, "get_project", lambda: {"name": "mq-mcp", "path": "/x"}
    )
    monkeypatch.setattr(bridge.bridget_runtime, "current_branch", lambda p: "main")
    monkeypatch.setattr(bridge.time, "monotonic", lambda: 100.0)
    ctx = _RecordingCtx()

    bridge.record_chat_session(
        ctx,
        do_mode=True,
        turns=3,
        tools=["alpha", "beta"],
        last_prompt="senaste frågan",
        last_answer="senaste svaret",
        start=90.0,
    )

    assert len(ctx.calls) == 1
    prompt, tools, answer, kw = ctx.calls[0]
    assert (prompt, tools, answer) == ("senaste frågan", ["alpha", "beta"], "senaste svaret")
    assert kw["chat_mode"] is True
    assert kw["do_mode"] is True
    assert kw["turns"] == 3
    assert kw["duration_s"] == 10.0
    assert kw["project"] == "mq-mcp"
    assert kw["branch"] == "main"


def test_record_chat_session_skips_empty_session(bridge, monkeypatch):
    # A session that never ran a model turn must not touch memory at all —
    # get_project is never even consulted.
    monkeypatch.setattr(
        bridge.bridget_runtime,
        "get_project",
        lambda: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    ctx = _RecordingCtx()

    bridge.record_chat_session(
        ctx,
        do_mode=False,
        turns=0,
        tools=[],
        last_prompt="",
        last_answer="",
        start=0.0,
    )

    assert ctx.calls == []


def test_record_chat_session_no_project_pin(bridge, monkeypatch):
    monkeypatch.setattr(bridge.bridget_runtime, "get_project", lambda: None)
    ctx = _RecordingCtx()

    bridge.record_chat_session(
        ctx,
        do_mode=False,
        turns=1,
        tools=[],
        last_prompt="p",
        last_answer="a",
        start=0.0,
    )

    assert len(ctx.calls) == 1
    _, _, _, kw = ctx.calls[0]
    assert kw["project"] is None
    assert kw["branch"] is None
    assert kw["chat_mode"] is True


# --- print_response ------------------------------------------------------------


def test_print_response_plain_prefix(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "speak_if_enabled", lambda *_a, **_k: None)
    buf = io.StringIO()  # no isatty -> scramble_print writes plain text
    monkeypatch.setattr(bridge.sys, "stdout", buf)

    bridge.print_response("answer text", prefix_newline=False)

    assert buf.getvalue() == "👩 Bridget: answer text\n"


def test_print_response_newline_prefix(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "speak_if_enabled", lambda *_a, **_k: None)
    buf = io.StringIO()
    monkeypatch.setattr(bridge.sys, "stdout", buf)

    bridge.print_response("x", prefix_newline=True)

    assert buf.getvalue() == "\n👩 Bridget: x\n"


# --- Phase 3: context window management ----------------------------------------


def test_estimate_tokens_counts_content_and_tool_calls(bridge):
    msgs = [
        {"role": "system", "content": "a" * 40},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "xxxx", "arguments": "yyyy"}}],
        },
    ]
    # 40 content chars + 4 name + 4 args = 48 chars // 4 = 12
    assert bridge.estimate_tokens(msgs) == 12


def test_context_budget_env_override_wins(bridge, monkeypatch):
    monkeypatch.setenv("BRIDGET_CONTEXT_BUDGET", "1234")
    assert bridge.context_budget_for("gpt-5.4-mini") == 1234


def test_context_budget_per_model_defaults(bridge, monkeypatch):
    monkeypatch.delenv("BRIDGET_CONTEXT_BUDGET", raising=False)
    # mini is checked first, so mini variants get the smaller budget
    assert bridge.context_budget_for("gpt-5.4-mini") == 60_000
    assert bridge.context_budget_for("gpt-5") == 120_000
    assert bridge.context_budget_for("o3") == 120_000
    assert bridge.context_budget_for("totally-unknown") == bridge.DEFAULT_CONTEXT_BUDGET


def test_truncate_tool_output(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "MAX_TOOL_OUTPUT_CHARS", 10)
    assert bridge.truncate_tool_output("abc") == "abc"
    out = bridge.truncate_tool_output("Z" * 25)
    assert out.startswith("Z" * 10)
    assert "trunkerat 15 tecken" in out


def test_trim_history_noop_when_small(bridge):
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    assert bridge.trim_history(msgs, budget_tokens=10**9) is msgs


def test_trim_history_keeps_system_and_recent_drops_middle(bridge):
    system = {"role": "system", "content": "SYS"}
    msgs = [system]
    for i in range(5):
        msgs.append({"role": "user", "content": f"u{i}"})
        msgs.append({"role": "assistant", "content": f"a{i}"})

    trimmed = bridge.trim_history(msgs, budget_tokens=10**9, max_messages=4)

    assert trimmed[0] is system
    assert any(
        "Earlier in this Bridget session" in (m.get("content") or "") for m in trimmed
    )
    # Most recent turn preserved; oldest turns dropped.
    assert trimmed[-1]["content"] == "a4"
    assert trimmed[-2]["content"] == "u4"
    assert len(trimmed) <= 4 + 1  # +1 for the summary note


def test_trim_history_preserves_tool_call_pairs(bridge):
    system = {"role": "system", "content": "SYS"}
    turn0 = [
        {"role": "user", "content": "old"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "t1", "function": {"name": "g", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "res"},
        {"role": "assistant", "content": "done"},
    ]
    turn1 = [
        {"role": "user", "content": "new"},
        {"role": "assistant", "content": "latest"},
    ]
    msgs = [system, *turn0, *turn1]

    # Tiny budget forces the oldest block out.
    trimmed = bridge.trim_history(msgs, budget_tokens=1, max_messages=100)

    roles = [m["role"] for m in trimmed]
    # The whole tool-bearing turn was dropped as a unit — no orphan tool message
    # and no dangling assistant tool_calls.
    assert "tool" not in roles
    assert not any(m.get("tool_calls") for m in trimmed)
    assert trimmed[-1]["content"] == "latest"


def test_execute_tool_calls_truncates_large_output(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "MAX_TOOL_OUTPUT_CHARS", 20)
    first = _response(_FakeMessage("", [_FakeToolCall("c1", "g", "{}")]))
    final = _response(_FakeMessage("ok", None))
    client = _FakeClient([first, final])
    session = _FakeSession(result_text="Z" * 100)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]

    asyncio.run(
        bridge.run_turn(
            client=client,
            model="m",
            messages=messages,
            openai_tools=[],
            do_mode=False,
            session=session,
        )
    )

    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["content"].startswith("Z" * 20)
    assert "trunkerat 80 tecken" in tool_msgs[0]["content"]
