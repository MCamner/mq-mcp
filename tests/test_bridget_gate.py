"""Tests for Bridget's class-based approval gate (v0.5).

Covers the pure safety-class lookup (bridget_safety) and the interactive gate
(bridge.approval_gate / render_gate_card). The gate must pass Class A/B silently
and require explicit consent for Class C/D and unknown tools.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "mq-mcp" / "bridge.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))

from bridget_safety import load_safety_map, needs_approval, tool_class


# --- pure safety-class lookup ------------------------------------------------


def test_real_contract_classifies_known_tools():
    smap = load_safety_map()
    assert len(smap) >= 100
    assert tool_class("read_repo_file", smap) == "A"
    assert needs_approval("read_repo_file", smap) is False  # A
    assert needs_approval("repo_signal_analyze", smap) is False  # B
    assert needs_approval("update_repo_file", smap) is True  # C
    assert needs_approval("shell_exec", smap) is True  # D


def test_unknown_tool_requires_approval():
    smap = load_safety_map()
    assert tool_class("does_not_exist", smap) == "unknown"
    assert needs_approval("does_not_exist", smap) is True


def test_missing_contract_degrades_to_ask(tmp_path):
    smap = load_safety_map(tmp_path / "absent.json")
    assert smap == {}
    # No contract -> classify everything as needing approval (fail-safe).
    assert needs_approval("anything", smap) is True


# --- interactive gate --------------------------------------------------------


@pytest.fixture()
def bridge():
    sys.modules.setdefault(
        "mcp", types.SimpleNamespace(ClientSession=object, StdioServerParameters=object)
    )
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_gate", BRIDGE_PATH)
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


def test_class_ab_passes_without_prompt(bridge, monkeypatch):
    prompts = _script(monkeypatch, bridge, ["nej"])  # would deny if ever asked
    monkeypatch.setattr(
        bridge, "_SMAP", {"read_repo_file": {"class": "A", "write": False, "subprocess": False}}
    )
    assert bridge.approval_gate("read_repo_file", {}) is True
    assert prompts == []  # never prompted


def test_class_d_approve(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["ja"])
    monkeypatch.setattr(
        bridge, "_SMAP", {"shell_exec": {"class": "D", "write": False, "subprocess": True}}
    )
    assert bridge.approval_gate("shell_exec", {"command": "ls"}) is True


def test_class_d_deny(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["nej"])
    monkeypatch.setattr(
        bridge, "_SMAP", {"shell_exec": {"class": "D", "write": False, "subprocess": True}}
    )
    assert bridge.approval_gate("shell_exec", {"command": "rm -rf /"}) is False


def test_empty_answer_denies(bridge, monkeypatch):
    _script(monkeypatch, bridge, [""])  # EOF / no tty
    monkeypatch.setattr(
        bridge, "_SMAP", {"shell_exec": {"class": "D", "write": False, "subprocess": True}}
    )
    assert bridge.approval_gate("shell_exec", {"command": "ls"}) is False


def test_show_then_approve_shows_verbose_args(bridge, monkeypatch):
    prompts = _script(monkeypatch, bridge, ["visa", "ja"])
    monkeypatch.setattr(
        bridge, "_SMAP", {"shell_exec": {"class": "D", "write": False, "subprocess": True}}
    )
    assert bridge.approval_gate("shell_exec", {"command": "ls", "flag": "x"}) is True
    # Second prompt is the verbose card with the full args dump.
    assert "args:" in prompts[1]
    assert "flag" in prompts[1]


def test_modify_edits_shell_command(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["ändra", "echo safe", "ja"])
    monkeypatch.setattr(
        bridge, "_SMAP", {"shell_exec": {"class": "D", "write": False, "subprocess": True}}
    )
    args = {"command": "rm -rf /"}
    assert bridge.approval_gate("shell_exec", args) is True
    assert args["command"] == "echo safe"


def test_unknown_tool_is_gated(bridge, monkeypatch):
    _script(monkeypatch, bridge, ["nej"])
    monkeypatch.setattr(bridge, "_SMAP", {})
    assert bridge.approval_gate("mystery_tool", {}) is False


def test_card_shows_class_and_flags(bridge, monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_SMAP",
        {"update_repo_file": {"class": "C", "write": True, "subprocess": False}},
    )
    card = bridge.render_gate_card(
        "update_repo_file", {"path": "x"}, "C", "uppdaterar fil"
    )
    assert "update_repo_file" in card
    assert "Klass:      C" in card
    assert "Skriver:    ja" in card
    assert "uppdaterar fil" in card
