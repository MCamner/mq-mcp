"""Tests for Bridget's REPL turn engine (v0.5).

run_turn is the core of the REPL: it runs one assistant turn against an
in-memory `messages` list and mutates it in place. Follow-up continuity falls
out of that — a short reply on the next turn carries the prior turn's context
because both turns share the same growing list.
"""

import asyncio
import importlib.util
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
        "mcp", types.SimpleNamespace(ClientSession=object, StdioServerParameters=object)
    )
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_repl", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- fake OpenAI client ------------------------------------------------------


class _Msg:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Resp:
    def __init__(self, msg):
        self.choices = [types.SimpleNamespace(message=msg)]


class _FakeClient:
    """Records the messages seen by each create() call; returns scripted msgs."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, model, messages, tools=None, tool_choice=None):
        self.calls.append([dict(m) for m in messages])
        return _Resp(self._responses.pop(0))


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = types.SimpleNamespace(name=name, arguments=arguments)

    def model_dump(self, exclude_none=False):
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


# --- tests -------------------------------------------------------------------


def test_followup_keeps_context(bridge):
    client = _FakeClient([_Msg("Vilket repo — mq-agent eller mq-mcp?"), _Msg("Kollar mq-mcp.")])
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "kolla repo och föreslå förbättringar"},
    ]

    ans1, tools1 = asyncio.run(
        bridge.run_turn(None, client, messages, "m", [], do_mode=False, spinner=None)
    )
    assert ans1 == "Vilket repo — mq-agent eller mq-mcp?"
    assert tools1 == []

    # Short follow-up reply — the whole point of the REPL.
    messages.append({"role": "user", "content": "mq-mcp"})
    ans2, _ = asyncio.run(
        bridge.run_turn(None, client, messages, "m", [], do_mode=False, spinner=None)
    )
    assert ans2 == "Kollar mq-mcp."

    # The second model call saw the full history: original goal, follow-up
    # question, and the short answer.
    second_call_contents = [m["content"] for m in client.calls[1]]
    assert "kolla repo och föreslå förbättringar" in second_call_contents
    assert "Vilket repo — mq-agent eller mq-mcp?" in second_call_contents
    assert "mq-mcp" in second_call_contents


def test_tool_call_path_records_result(bridge, monkeypatch):
    tc = _FakeToolCall("c1", "git_status", "{}")
    client = _FakeClient([_Msg("kollar status", tool_calls=[tc]), _Msg("Allt rent.")])

    async def fake_call(session, name, raw_args, assistant_note=""):
        assert name == "git_status"
        return "working tree clean"

    monkeypatch.setattr(bridge, "call_mcp_tool", fake_call)

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "git status?"},
    ]
    answer, called = asyncio.run(
        bridge.run_turn(None, client, messages, "m", [], do_mode=False, spinner=None)
    )

    assert answer == "Allt rent."
    assert called == ["git_status"]
    assert any(
        m.get("role") == "tool" and m["content"] == "working tree clean" for m in messages
    )


class _ACM:
    """Minimal async context manager yielding a fixed value."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    async def initialize(self):
        pass

    async def list_tools(self):
        return types.SimpleNamespace(tools=[])


class _FakeCtx:
    def __init__(self):
        self.recorded = []

    def load(self):
        return ""

    def load_lessons(self):
        return ""

    def record(self, prompt, tools, answer):
        self.recorded.append(prompt)


def test_repl_clear_drops_prior_turns(bridge, monkeypatch):
    """After /clear, the next turn's history no longer carries earlier turns."""
    client = _FakeClient([_Msg("svar ett"), _Msg("svar två")])

    monkeypatch.setattr(bridge, "OpenAI", lambda: client)
    monkeypatch.setattr(bridge, "BridgetContext", _FakeCtx)
    monkeypatch.setattr(bridge, "StdioServerParameters", lambda **kw: None)
    monkeypatch.setattr(bridge, "stdio_client", lambda params: _ACM((None, None)))
    monkeypatch.setattr(bridge, "ClientSession", lambda read, write: _ACM(_FakeSession()))

    lines = iter(["hej", "/clear", "igen", "/exit"])
    monkeypatch.setattr(bridge, "_ask_tty", lambda prompt: next(lines))

    asyncio.run(bridge.run_repl("m", do_mode=False))

    # Two model turns ran ("hej" and "igen"); "/clear" and "/exit" did not call.
    assert len(client.calls) == 2
    second_turn_contents = [m["content"] for m in client.calls[1]]
    assert "igen" in second_turn_contents
    assert "hej" not in second_turn_contents  # cleared before the second turn
