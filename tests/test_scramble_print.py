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
    sys.modules.setdefault("mcp", types.SimpleNamespace(ClientSession=object, StdioServerParameters=object))
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_scramble", BRIDGE_PATH)
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


class _StopAfterWaits:
    def __init__(self, max_waits: int = 1):
        self.max_waits = max_waits
        self.calls = 0

    def is_set(self) -> bool:
        return self.calls >= self.max_waits

    def wait(self, _interval: float) -> None:
        self.calls += 1


def test_bridget_spinner_uses_one_line_green_four_dot_blink(bridge):
    buf = _Tty()
    spinner = bridge.BridgetSpinner(stream=buf)
    spinner._stop_event = _StopAfterWaits(max_waits=5)

    spinner._spin()

    raw = buf.getvalue()
    assert "\033[38;5;82m" in raw
    assert "    \033[0m" in raw
    assert "•   \033[0m" in raw
    assert "••  \033[0m" in raw
    assert "••• \033[0m" in raw
    assert "••••\033[0m" in raw
    assert "\n" not in raw
    assert "\033[1A" not in raw
