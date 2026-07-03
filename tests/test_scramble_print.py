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

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_scramble", BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_non_tty_output_is_plain_text(bridge):
    buf = io.StringIO()
    bridge.scramble_print("hej värld", file=buf)
    assert buf.getvalue() == "hej värld\n"


def test_non_tty_output_has_no_backspaces(bridge):
    buf = io.StringIO()
    bridge.scramble_print("README summary", file=buf)
    assert "\b" not in buf.getvalue()


def test_tty_output_animates_and_resolves(bridge, monkeypatch):
    monkeypatch.setattr(bridge.time, "sleep", lambda _s: None)
    buf = _Tty()
    bridge.scramble_print("ab", file=buf)
    raw = buf.getvalue()
    assert raw.count("\b") == 6
    # What a terminal would render: backspace removes the char before it.
    rendered = []
    for ch in raw:
        if ch == "\b":
            rendered.pop()
        else:
            rendered.append(ch)
    assert "".join(rendered) == "ab\n"
