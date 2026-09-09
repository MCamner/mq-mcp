"""One bad byte on stdin must not end a Bridget session.

Regression for a crash in the interactive REPL: under a UTF-8 locale Python
decodes stdin strictly, so an invalid byte raised UnicodeDecodeError inside
``sys.stdin.readline()``. The REPL runs inside the MCP client session and the
stdio task group, so the error surfaced as a nested ExceptionGroup traceback
and took the whole bridge down — over input the operator could have retyped.
"""

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
    mcp_stub: Any = types.ModuleType("mcp")
    mcp_stub.ClientSession = object
    mcp_stub.StdioServerParameters = object
    sys.modules.setdefault("mcp", mcp_stub)
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio: Any = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_stdin", BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Raising:
    """A stream whose readline fails the way a strict decoder fails."""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def readline(self) -> str:
        raise self.exc


def test_a_line_is_the_turn_stripped(bridge):
    out = io.StringIO()
    assert bridge.read_operator_line(io.StringIO("  status i mq-hal  \n"), out) == (
        "status i mq-hal"
    )
    assert out.getvalue() == ""


def test_end_of_input_ends_the_session(bridge):
    assert bridge.read_operator_line(io.StringIO(""), io.StringIO()) is None


def test_ctrl_c_at_the_prompt_ends_the_session(bridge):
    stream = Raising(KeyboardInterrupt())
    assert bridge.read_operator_line(stream, io.StringIO()) is None


def test_an_undecodable_line_is_skipped_not_fatal(bridge):
    out = io.StringIO()
    exc = UnicodeDecodeError("utf-8", b"\xc3(", 0, 1, "invalid continuation byte")
    # Empty string, so the REPL's `if not user_input: continue` skips the turn
    # and prompts again. None would have ended the session instead.
    assert bridge.read_operator_line(Raising(exc), out) == ""
    assert "UTF-8" in out.getvalue()


def test_the_reported_crash_no_longer_escapes(bridge):
    """The exact shape that killed the bridge: strict UTF-8 over a bad byte."""
    raw = io.BytesIO("vad hände med det".encode()[:18] + b"\xc3(ello\n")
    stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")

    # Without the fix this raises out of readline and, in the REPL, out of two
    # nested task groups.
    assert bridge.read_operator_line(stream, io.StringIO()) == ""


def test_a_replacing_stream_keeps_the_readable_part(bridge):
    """What the process actually gets after __main__ reconfigures stdin."""
    raw = io.BytesIO(b"vad h\xc3nde med mq-hal\n")
    stream = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")

    turn = bridge.read_operator_line(stream, io.StringIO())
    assert turn is not None and turn.startswith("vad h") and turn.endswith("mq-hal")
