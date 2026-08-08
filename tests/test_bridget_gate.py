"""Tests for Bridget's effect-based approval gate.

The gate asks before a tool that writes or runs something, and stays quiet for
read-only tools. Class alone is the wrong signal: 27 Class A/B tools (git_status,
git_diff, check_port, get_battery_status …) are implemented as subprocesses while
being strictly read-only, so gating on `subprocess` would interrupt ordinary
reads. The rule is: write ⇒ ask; Class D ⇒ ask unless cosmetic; unknown ⇒ ask.
"""

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "mq-mcp" / "bridge.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))

from bridget_safety import load_safety_map, needs_approval, tool_class

# --- pure lookup ------------------------------------------------------------

def test_real_contract_loads():
    smap = load_safety_map()
    assert len(smap) >= 100
    assert tool_class("read_repo_file", smap) == "A"


def test_read_only_tools_pass():
    smap = load_safety_map()
    assert needs_approval("read_repo_file", smap) is False
    assert needs_approval("repo_signal_analyze", smap) is False


def test_read_only_subprocess_tools_pass():
    # The whole point of the effect-based rule: these shell out but change nothing.
    smap = load_safety_map()
    for name in ("git_status", "git_diff", "check_port", "get_battery_status"):
        assert needs_approval(name, smap) is False, name


def test_writing_tools_are_gated():
    smap = load_safety_map()
    for name in ("update_repo_file", "edit_image", "record_learning", "take_screenshot"):
        assert needs_approval(name, smap) is True, name


def test_executing_tools_are_gated():
    smap = load_safety_map()
    for name in ("shell_exec", "run_tests", "run_mqlaunch", "open_repo_terminal"):
        assert needs_approval(name, smap) is True, name


def test_cosmetic_tools_pass():
    # Class D, but nothing survives the call: no file, no process, no state.
    smap = load_safety_map()
    for name in ("set_volume", "speak_text", "show_notification", "toggle_dark_mode"):
        assert needs_approval(name, smap) is False, name


def test_unknown_tool_requires_approval():
    smap = load_safety_map()
    assert tool_class("does_not_exist", smap) == "unknown"
    assert needs_approval("does_not_exist", smap) is True


def test_missing_contract_degrades_to_ask(tmp_path):
    smap = load_safety_map(tmp_path / "absent.json")
    assert smap == {}
    assert needs_approval("anything", smap) is True


def test_high_risk_tools_named_in_safety_model_are_all_gated():
    # SAFETY_MODEL.md lists these four under "High-risk areas".
    smap = load_safety_map()
    for name in ("update_repo_file", "run_mqlaunch", "edit_image", "open_in_app"):
        assert needs_approval(name, smap) is True, name


# --- interactive gate -------------------------------------------------------

@pytest.fixture()
def bridge():
    mcp_stub: Any = types.ModuleType("mcp")
    mcp_stub.ClientSession = object
    mcp_stub.StdioServerParameters = object
    sys.modules.setdefault("mcp", mcp_stub)
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio: Any = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_gate", BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _script(monkeypatch, bridge, answers):
    """Feed scripted answers to the gate's tty reader; record the prompts shown."""
    it = iter(answers)
    prompts: list[str] = []

    def fake_ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(it)

    monkeypatch.setattr(bridge, "_ask_tty", fake_ask)
    return prompts


_READ_ONLY = {"read_repo_file": {"class": "A", "write": False, "subprocess": False}}
_WRITER = {"update_repo_file": {"class": "C", "write": True, "subprocess": False}}
_SHELL = {"shell_exec": {"class": "D", "write": False, "subprocess": True}}


def test_gate_passes_read_only_without_prompting(bridge, monkeypatch):
    prompts = _script(monkeypatch, bridge, ["nej"])  # would deny if ever asked
    monkeypatch.setattr(bridge, "_SMAP", _READ_ONLY)
    assert bridge.approval_gate("read_repo_file", {}) is True
    assert prompts == []


def test_gate_approves_on_yes(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["ja"])
    monkeypatch.setattr(bridge, "_SMAP", _SHELL)
    assert bridge.approval_gate("shell_exec", {"command": "ls"}) is True


def test_gate_denies_on_no(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["nej"])
    monkeypatch.setattr(bridge, "_SMAP", _SHELL)
    assert bridge.approval_gate("shell_exec", {"command": "rm -rf /"}) is False


def test_empty_answer_denies(bridge, monkeypatch):
    # EOF or no tty must never be read as consent.
    _script(monkeypatch, bridge, [""])
    monkeypatch.setattr(bridge, "_SMAP", _SHELL)
    assert bridge.approval_gate("shell_exec", {"command": "ls"}) is False


def test_show_then_approve_reveals_full_args(bridge, monkeypatch):
    prompts = _script(monkeypatch, bridge, ["visa", "ja"])
    monkeypatch.setattr(bridge, "_SMAP", _SHELL)
    assert bridge.approval_gate("shell_exec", {"command": "ls", "flag": "x"}) is True
    assert "args:" in prompts[1]
    assert "flag" in prompts[1]


def test_modify_edits_the_shell_command(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["ändra", "echo safe", "ja"])
    monkeypatch.setattr(bridge, "_SMAP", _SHELL)
    args = {"command": "rm -rf /"}
    assert bridge.approval_gate("shell_exec", args) is True
    assert args["command"] == "echo safe"


def test_unrecognized_answer_reprompts_rather_than_guessing(bridge, monkeypatch):
    prompts = _script(monkeypatch, bridge, ["kanske", "nej"])
    monkeypatch.setattr(bridge, "_SMAP", _SHELL)
    assert bridge.approval_gate("shell_exec", {"command": "ls"}) is False
    assert len(prompts) == 2


def test_unknown_tool_is_gated(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["nej"])
    monkeypatch.setattr(bridge, "_SMAP", {})
    assert bridge.approval_gate("mystery_tool", {}) is False


def test_card_states_what_the_tool_does(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "_SMAP", _WRITER)
    card = bridge.render_gate_card("update_repo_file", {"path": "x"}, "C")
    assert "update_repo_file" in card
    assert "Klass:      C" in card
    assert "Skriver:    ja" in card
