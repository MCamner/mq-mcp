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


@pytest.fixture(autouse=True)
def _open_gate(bridge, monkeypatch):
    """Let tool calls through so these tests exercise the loop, not consent.

    The tests drive the loop with invented tool names (alpha, beta, g), which
    the approval gate correctly treats as unknown and therefore gates. Consent
    behavior has its own tests in test_bridget_gate.py.
    """
    monkeypatch.setattr(bridge, "approval_gate", lambda *args, **kwargs: True)


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


def test_openai_tool_specs_exclude_only_compatibility_aliases(bridge):
    excluded = {
        "explain_learned_pattern",
        "learn_status",
        "search_learned_patterns",
    }
    tools = [
        types.SimpleNamespace(
            name=name,
            description=name,
            inputSchema={"type": "object", "properties": {}},
        )
        for name in [*sorted(excluded), *[f"tool_{index}" for index in range(127)]]
    ]

    openai_tools = bridge.to_openai_tools(types.SimpleNamespace(tools=tools))
    names = {item["function"]["name"] for item in openai_tools}

    assert len(openai_tools) == 127
    assert not names & excluded
    assert "tool_126" in names


# --- build_system_content ------------------------------------------------------


def _fake_ctx(session="", lessons="", calls=None):
    def load_lessons(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return lessons

    return types.SimpleNamespace(load=lambda: session, load_lessons=load_lessons)


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


def test_build_system_content_passes_repo_file_and_task_to_lessons(bridge, monkeypatch):
    calls = []
    ctx = _fake_ctx(lessons="LESSON", calls=calls)
    monkeypatch.setattr(bridge.bridget_runtime, "project_context_block", lambda: "")
    monkeypatch.setattr(
        bridge, "lesson_context_filters", lambda task: ("mq-mcp", "mq-mcp/server.py")
    )

    bridge.build_system_content(
        ctx, "catalog", do_mode=False, task="fix mq-mcp/server.py contract"
    )

    assert calls == [{
        "repo": "mq-mcp",
        "file_path": "mq-mcp/server.py",
        "task": "fix mq-mcp/server.py contract",
    }]


def test_refresh_system_message_replaces_context_without_growth(bridge, monkeypatch):
    monkeypatch.setattr(bridge.bridget_runtime, "project_context_block", lambda: "")
    monkeypatch.setattr(bridge, "lesson_context_filters", lambda task: ("mq-mcp", ""))
    calls = []
    ctx = _fake_ctx(lessons="LESSON", calls=calls)
    messages = [
        {"role": "system", "content": "old"},
        {"role": "user", "content": "previous turn"},
    ]

    bridge.refresh_system_message(messages, ctx, "catalog", False, "new task")

    assert len(messages) == 2
    assert messages[0]["content"] != "old"
    assert calls[-1]["task"] == "new task"


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


# --- Phase 1: preview-only learn suggestions ---------------------------------


def test_build_learn_suggestion_requires_evidence_tool(bridge):
    assert bridge.build_learn_suggestion("task", "answer", ["search_repo"]) == ""
    assert bridge.build_learn_suggestion("task", "answer", []) == ""
    assert bridge.build_learn_suggestion("prior session", "context", ["git_status"]) == ""


def test_build_learn_suggestion_is_bounded_and_never_claims_storage(bridge):
    suggestion = bridge.build_learn_suggestion(
        "fix the repeated issue " * 20,
        "the reusable result " * 80,
        ["review_diff", "validate_project"],
    )

    assert "Reusable learn candidate" in suggestion
    assert "review_diff, validate_project" in suggestion
    assert "stored: false" in suggestion
    assert "explicit approval" in suggestion
    assert len(suggestion) <= bridge.MAX_LEARN_SUGGESTION_CHARS


def test_build_learn_suggestion_suppressed_after_learn_write(bridge):
    suggestion = bridge.build_learn_suggestion(
        "task", "answer", ["review_diff", "learn_from_diff"]
    )
    assert suggestion == ""


def test_print_learn_suggestion_emits_one_preview(bridge):
    out = io.StringIO()
    bridge.print_learn_suggestion(
        "task", "answer", ["run_tests", "run_tests"], out=out
    )

    assert out.getvalue().count("Reusable learn candidate") == 1


def test_print_delegation_suggestion_emits_preview_without_starting_workflow(bridge):
    out = io.StringIO()

    emitted = bridge.print_delegation_suggestion(
        "Update mq-mcp and mq-agent, then validate both",
        out=out,
    )

    assert emitted is True
    assert out.getvalue().count("Delegation suggestion") == 1


def test_parse_learn_last_args_accepts_optional_review_path(bridge):
    assert bridge.parse_learn_last_args(["--learn-last"]) == ""
    assert bridge.parse_learn_last_args(["--learn-last", "mq-mcp/server.py"]) == (
        "mq-mcp/server.py"
    )


def test_parse_learn_last_args_rejects_extra_arguments(bridge):
    with pytest.raises(ValueError, match="at most one"):
        bridge.parse_learn_last_args(["--learn-last", "a.py", "b.py"])


def test_redact_learn_preview_masks_secret_values(bridge):
    preview = bridge.redact_learn_preview(
        "token=abc123 password:letmein Bearer private.jwt.value"
    )

    assert "abc123" not in preview
    assert "letmein" not in preview
    assert "private.jwt.value" not in preview
    assert "<redacted>" in preview


def test_latest_review_path_uses_active_repo_namespace(bridge, monkeypatch, tmp_path):
    history = tmp_path / "review_history.json"
    history.write_text(
        '{"mq-mcp":{"server.py":[{"file_path":"server.py","timestamp":2}]},'
        '"mq-hal":{"README.md":[{"file_path":"README.md","timestamp":3}]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge, "REVIEW_HISTORY_FILE", history)

    assert bridge._latest_review_path(Path("/tmp/mq-hal")) == "README.md"


def test_run_learn_last_denial_keeps_review_as_dry_run(bridge, monkeypatch):
    session = _FakeSession(result_text="preview token=abc123")
    out = io.StringIO()
    monkeypatch.setattr(
        bridge, "resolve_learn_last_context", lambda _path="": ("server.py", "/repo")
    )
    monkeypatch.setattr(bridge, "approval_gate", lambda *_a, **_k: False)

    asyncio.run(bridge.run_learn_last(session, out=out))

    assert session.tool_calls == [
        ("learn_extract_from_last_review", {"relative_path": "server.py", "repo_path": "/repo"})
    ]
    assert "abc123" not in out.getvalue()
    assert "stored: false" in out.getvalue()


def test_run_learn_last_approval_stores_via_existing_review_tool(bridge, monkeypatch):
    session = _FakeSession(result_text="safe preview")
    monkeypatch.setattr(
        bridge, "resolve_learn_last_context", lambda _path="": ("server.py", "/repo")
    )
    monkeypatch.setattr(bridge, "approval_gate", lambda *_a, **_k: True)

    asyncio.run(bridge.run_learn_last(session, out=io.StringIO()))

    assert session.tool_calls == [
        ("learn_extract_from_last_review", {"relative_path": "server.py", "repo_path": "/repo"}),
        (
            "learn_from_review",
            {
                "relative_path": "server.py",
                "repo_path": "/repo",
                "learning_origin": "bridget",
            },
        ),
    ]


def test_run_learn_last_falls_back_to_redacted_diff_preview(bridge, monkeypatch):
    session = _FakeSession(result_text="stored")
    out = io.StringIO()
    monkeypatch.setattr(bridge, "resolve_learn_last_context", lambda _path="": ("", "/repo"))
    monkeypatch.setattr(
        bridge,
        "build_diff_learn_args",
        lambda _repo: {
            "task": "fix token=abc123",
            "lesson": "keep password=letmein out",
            "validation": "changed: bridge.py",
            "risk": "unknown",
        },
    )
    monkeypatch.setattr(bridge, "approval_gate", lambda *_a, **_k: False)

    asyncio.run(bridge.run_learn_last(session, out=out))

    assert session.tool_calls == []
    assert "source: diff" in out.getvalue()
    assert "abc123" not in out.getvalue()
    assert "letmein" not in out.getvalue()
    assert "stored: false" in out.getvalue()


def test_run_learn_last_approved_diff_is_attributed_to_bridget(bridge, monkeypatch):
    session = _FakeSession(result_text="stored")
    monkeypatch.setattr(bridge, "resolve_learn_last_context", lambda _path="": ("", "/repo"))
    monkeypatch.setattr(
        bridge,
        "build_diff_learn_args",
        lambda _repo: {
            "task": "fix contract",
            "lesson": "keep provenance",
            "validation": "changed: bridge.py",
            "risk": "unknown",
        },
    )
    monkeypatch.setattr(bridge, "approval_gate", lambda *_a, **_k: True)

    asyncio.run(bridge.run_learn_last(session, out=io.StringIO()))

    assert session.tool_calls == [
        (
            "learn_from_diff",
            {
                "task": "fix contract",
                "lesson": "keep provenance",
                "validation": "changed: bridge.py",
                "risk": "unknown",
                "learning_origin": "bridget",
            },
        )
    ]


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
