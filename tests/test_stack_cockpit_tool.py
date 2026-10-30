from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "stack_bridge.py"
SERVER_PATH = ROOT / "mq-mcp" / "server.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("mq_mcp_stack_bridge_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registered_tool_names() -> set[str]:
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "tool"
            for decorator in node.decorator_list
        )
    }


def _cockpit() -> dict:
    return {
        "schema": "mq_stack_cockpit.v1",
        "overall_gate": "GO",
        "overall_contract": "READY",
        "repos": [{"repo": "mq-mcp", "gate": "GO"}],
    }


def test_cockpit_uses_fixed_uv_command_without_shell(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, json.dumps(_cockpit()), "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.cockpit()

    assert result == _cockpit()
    assert captured["command"] == [
        "uv",
        "--project",
        str(agent_home),
        "run",
        "mq-agent",
        "stack",
        "cockpit",
        "--json",
    ]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["cwd"] == agent_home


def test_cockpit_errors_are_bounded_and_do_not_leak_output(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, "PRIVATE-STDOUT", "PRIVATE-STDERR"
        ),
    )

    result = module.cockpit()

    assert result == {
        "schema": "mq.stack-tool-error.v1",
        "status": "UNAVAILABLE",
        "error_code": "mq-agent-stack-failed",
    }
    assert "PRIVATE" not in json.dumps(result)


def test_cockpit_rejects_non_json_output(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "not json", ""),
    )

    assert module.cockpit()["error_code"] == "mq-agent-invalid-json"


def test_cockpit_reports_missing_agent_home(monkeypatch, tmp_path) -> None:
    module = _load_module()
    monkeypatch.setenv("MQ_AGENT_HOME", str(tmp_path / "absent"))

    assert module.cockpit()["error_code"] == "mq-agent-unavailable"


def test_cockpit_reports_timeout(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.cockpit()["error_code"] == "mq-agent-timeout"


def test_mq_stack_cockpit_is_registered_without_parameters() -> None:
    assert "mq_stack_cockpit" in _registered_tool_names()
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "mq_stack_cockpit"
    )
    assert node.args.args == []
