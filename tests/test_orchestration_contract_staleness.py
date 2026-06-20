"""Regression tests for validate_orchestration_contract staleness gating.

A bare mtime comparison (contract older than server.py) used to emit a [WARN]
on any checkout/clone or unrelated server.py edit, even when the tool set was
unchanged. The staleness WARN must now fire only on a real tool delta (tools
added or removed since the contract's last commit).
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import server  # noqa: E402

SERVER_PATH = ROOT / "mq-mcp" / "server.py"
CONTRACT_PATH = ROOT / "docs" / "ORCHESTRATION_CONTRACT.md"


def _current_tool_names() -> set[str]:
    src = SERVER_PATH.read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                attr = dec.func if isinstance(dec, ast.Call) else dec
                if (
                    isinstance(attr, ast.Attribute)
                    and attr.attr == "tool"
                    and isinstance(attr.value, ast.Name)
                    and attr.value.id == "mcp"
                ):
                    names.add(node.name)
    return names


def _fake_server_src(tool_names) -> str:
    header = (
        "class _M:\n"
        "    def tool(self, *a, **k):\n"
        "        return lambda f: f\n"
        "mcp = _M()\n"
    )
    body = "".join(f"@mcp.tool()\ndef {n}():\n    pass\n" for n in sorted(tool_names))
    return header + body


def _patch(monkeypatch, old_tool_names) -> None:
    """Force: contract mtime older than server.py, and the contract's
    last-commit server.py exposing exactly ``old_tool_names``."""
    s = SERVER_PATH.stat()
    os.utime(CONTRACT_PATH, (s.st_atime - 100, s.st_mtime - 100))

    fake_src = _fake_server_src(old_tool_names)
    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        class _R:
            returncode = 0
            stdout = ""

        if cmd[:2] == ["git", "log"]:
            _R.stdout = "deadbeefcafebabe\n"
            return _R
        if cmd[:2] == ["git", "show"]:
            _R.stdout = fake_src
            return _R
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_no_warn_when_mtime_newer_but_tool_set_unchanged(monkeypatch):
    _patch(monkeypatch, _current_tool_names())
    out = server.validate_orchestration_contract()
    assert "[WARN] docs/ORCHESTRATION_CONTRACT.md" not in out
    assert "no tool drift" in out


def test_warn_when_tool_added_since_contract(monkeypatch):
    current = _current_tool_names()
    assert current, "expected at least one registered tool"
    dropped = sorted(current)[0]
    _patch(monkeypatch, current - {dropped})
    out = server.validate_orchestration_contract()
    assert "[WARN] docs/ORCHESTRATION_CONTRACT.md" in out
    assert "no longer reflects the current tool set" in out
    assert dropped in out
