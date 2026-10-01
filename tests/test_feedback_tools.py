from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "feedback_bridge.py"
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
READ_TOOLS = {
    "mq_feedback_status",
    "mq_feedback_inspect",
    "mq_feedback_compare",
    "mq_feedback_report",
    "mq_feedback_candidates",
}
ALL_TOOLS = READ_TOOLS | {"mq_feedback_run"}


def _load_module():
    spec = importlib.util.spec_from_file_location("mq_mcp_feedback_bridge_test", MODULE_PATH)
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


def test_feedback_bridge_uses_fixed_uv_command_without_shell(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"view": "feedback-status.v1", "health": "HEALTHY"}),
            "",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.status()

    assert result["health"] == "HEALTHY"
    assert captured["command"] == [
        "uv",
        "--project",
        str(agent_home),
        "run",
        "mq-agent",
        "feedback",
        "status",
        "--json",
    ]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["cwd"] == agent_home


def test_feedback_bridge_errors_are_bounded_and_do_not_leak_output(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 2, "PRIVATE-STDOUT", "PRIVATE-STDERR"
        ),
    )

    result = module.report()

    assert result == {
        "schema": "mq.feedback-tool-error.v1",
        "status": "UNAVAILABLE",
        "error_code": "mq-agent-feedback-failed",
    }
    assert "PRIVATE" not in json.dumps(result)


def test_feedback_run_delegates_budgets_and_task_without_shell(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"status": "PASS", "experiment": {"feedback_run_id": "fb-1"}}),
            "",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.run(
        "review repo",
        repo="/safe/repo",
        timeout_ms=1500,
        max_context_bytes=4096,
        max_sources=12,
    )

    assert result["status"] == "PASS"
    assert captured["command"][-18:] == [
        "feedback",
        "run",
        "--task",
        "review repo",
        "--repo",
        "/safe/repo",
        "--task-class",
        "repo-review",
        "--timeout-ms",
        "1500",
        "--max-context-bytes",
        "4096",
        "--max-sources",
        "12",
        "--json",
    ]


def test_feedback_tools_are_registered_and_safety_classified() -> None:
    assert ALL_TOOLS <= _registered_tool_names()
    contracts = json.loads(
        (ROOT / "docs" / "tool_contracts.json").read_text(encoding="utf-8")
    )
    by_name = {item["name"]: item for item in contracts["tools"]}

    for name in READ_TOOLS:
        assert by_name[name]["class"] == "A"
        assert by_name[name]["write"] is False
        assert by_name[name]["subprocess"] is True
        assert by_name[name]["resolver"] == "mq_agent_feedback_bridge"
        assert by_name[name]["side_effects"] == []

    run = by_name["mq_feedback_run"]
    assert run["class"] == "C"
    assert run["write"] is True
    assert run["resolver"] == "resolve_allowed_local_file"
    assert run["side_effects"] == ["feedback-evidence-write", "bounded-compute"]


def test_no_feedback_activation_tool_exists() -> None:
    registered = _registered_tool_names()
    assert not {
        "mq_feedback_activate",
        "mq_feedback_candidate_state",
        "mq_feedback_purge",
        "mq_feedback_candidate_handoff",
    } & registered


def test_codex_and_claude_profiles_discover_same_feedback_tools() -> None:
    for profile_name in ("codex.json", "claude-desktop.json"):
        profile = json.loads((ROOT / "profiles" / profile_name).read_text(encoding="utf-8"))
        assert ALL_TOOLS <= set(profile["recommended_tools"])


def test_feedback_skill_is_symlinked_identically_for_codex_and_claude() -> None:
    canonical = ROOT / "skills" / "feedback-review"
    assert canonical.is_dir()
    for root in (ROOT / ".agents" / "skills", ROOT / ".claude" / "skills"):
        link = root / "feedback-review"
        assert link.is_symlink()
        assert link.resolve() == canonical.resolve()
