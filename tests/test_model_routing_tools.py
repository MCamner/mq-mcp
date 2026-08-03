from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "model_routing.py"
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
TOOL_NAMES = {
    "mq_route_inspect",
    "mq_route_shadow",
    "mq_context_pack",
    "mq_route_verify",
    "mq_route_report",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("mq_mcp_model_routing_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registered_tool_names() -> set[str]:
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "tool"
            for decorator in node.decorator_list
        ):
            names.add(node.name)
    return names


def _decision() -> dict:
    return {
        "schema": "mq.model-route-decision.v1",
        "decision_id": "route-test",
        "task_class": "docs-review",
        "risk": "low",
        "recommended_route": "local-shadow",
        "local_model": "qwen3:4b-instruct",
        "authoritative_agent": "codex",
        "reason_codes": ["read-only", "deterministic-verification-available"],
        "escalation_conditions": ["schema-invalid", "verification-failed"],
    }


def _candidate() -> dict:
    return {
        "task_class": "docs-review",
        "summary": "README and command surface agree.",
        "evidence": ["The route commands are documented."],
        "suggestions": [],
    }


def _outcome() -> dict:
    return {
        "schema": "mq.model-route-outcome.v1",
        "decision_id": "route-test",
        "task_class": "docs-review",
        "selected_route": "local-shadow",
        "local_model": "qwen3:4b-instruct",
        "authoritative_agent": "codex",
        "attempted": False,
        "model_output_received": False,
        "schema_valid": False,
        "verification": {"status": "UNAVAILABLE", "checks": []},
        "accepted_by_agent": False,
        "accepted_by_operator": False,
        "escalated": True,
        "escalation_reason": "model-unavailable",
        "recorded_at": "2026-08-03T12:00:00Z",
    }


def _copy_agent_schemas(agent_home: Path) -> None:
    target = agent_home / "schemas"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("model_route_decision.schema.json", "model_route_outcome.schema.json"):
        source = ROOT.parent / "mq-agent" / "schemas" / name
        (target / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def test_bridge_uses_fixed_uv_command_without_shell(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    _copy_agent_schemas(agent_home)
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, json.dumps(_decision()), "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.route_inspect("Review README", authoritative_agent="codex")

    assert result["status"] == "PASS"
    assert captured["command"] == [
        "uv",
        "--project",
        str(agent_home),
        "run",
        "mq-agent",
        "route",
        "inspect",
        "Review README",
        "--agent",
        "codex",
        "--json",
    ]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["cwd"] == agent_home


def test_missing_agent_returns_structured_unavailable(monkeypatch, tmp_path) -> None:
    module = _load_module()
    monkeypatch.setenv("MQ_AGENT_HOME", str(tmp_path / "missing"))

    result = module.route_inspect("Review README")

    assert result == {
        "schema": "mq.route-tool-result.v1",
        "tool": "mq_route_inspect",
        "status": "UNAVAILABLE",
        "data": None,
        "error_code": "mq-agent-unavailable",
    }


def test_malformed_agent_output_is_rejected_without_raw_text(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    agent_home.mkdir()
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "not-json-secret", ""),
    )

    result = module.route_report()

    assert result["status"] == "FAIL"
    assert result["error_code"] == "invalid-json"
    assert "not-json-secret" not in json.dumps(result)


def test_route_verify_accepts_valid_candidate_and_rejects_task_mismatch(tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    _copy_agent_schemas(agent_home)

    valid = module.route_verify(_decision(), _candidate(), agent_home=agent_home)
    mismatch = module.route_verify(
        _decision(),
        {**_candidate(), "task_class": "diff-summary"},
        agent_home=agent_home,
    )

    assert valid["status"] == "PASS"
    assert valid["data"]["verification"] == {
        "status": "PASS",
        "checks": ["decision-schema", "candidate-schema", "task-class-match"],
    }
    assert mismatch["status"] == "FAIL"
    assert mismatch["data"]["escalation_required"] is True
    assert "task-class-mismatch" in mismatch["data"]["errors"]


def test_shadow_propagates_structured_ollama_unavailable(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    _copy_agent_schemas(agent_home)
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    monkeypatch.setattr(
        module,
        "_run_agent_json",
        lambda *args, **kwargs: {
            "decision": _decision(),
            "candidate": None,
            "outcome": _outcome(),
        },
    )

    result = module.route_shadow("Review README")

    assert result["status"] == "UNAVAILABLE"
    assert result["error_code"] == "model-unavailable"
    assert result["data"]["candidate"] is None


def test_shadow_rejects_contract_drift(monkeypatch, tmp_path) -> None:
    module = _load_module()
    agent_home = tmp_path / "mq-agent"
    _copy_agent_schemas(agent_home)
    monkeypatch.setenv("MQ_AGENT_HOME", str(agent_home))
    monkeypatch.setattr(
        module,
        "_run_agent_json",
        lambda *args, **kwargs: {
            "decision": _decision(),
            "candidate": None,
            "outcome": {**_outcome(), "unexpected": True},
        },
    )

    result = module.route_shadow("Review README")

    assert result["status"] == "FAIL"
    assert result["data"] is None
    assert result["error_code"] == "contract-invalid"


def test_all_route_tools_are_registered_and_class_b() -> None:
    assert TOOL_NAMES <= _registered_tool_names()
    contracts = json.loads((ROOT / "docs" / "tool_contracts.json").read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in contracts["tools"]}
    for name in TOOL_NAMES:
        assert by_name[name]["class"] == "B"
        assert by_name[name]["write"] is False
        assert by_name[name]["side_effects"] == []


def test_codex_and_claude_profiles_recommend_same_route_tools() -> None:
    for profile_name in ("codex.json", "claude-desktop.json"):
        profile = json.loads((ROOT / "profiles" / profile_name).read_text(encoding="utf-8"))
        assert TOOL_NAMES <= set(profile["recommended_tools"])
