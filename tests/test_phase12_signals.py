import ast
import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "phase12_signals.py"
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
CONTRACTS_PATH = ROOT / "docs" / "tool_contracts.json"


def _load_phase12():
    spec = importlib.util.spec_from_file_location("phase12_signals", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["phase12_signals"] = module
    spec.loader.exec_module(module)
    return module


def _mcp_tool_names() -> set[str]:
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
            ):
                names.add(node.name)
    return names


def _load_server_with_stubbed_dependencies():
    class FakeMCP:
        def __init__(self, *args, **kwargs):
            pass

        def custom_route(self, *args, **kwargs):
            return lambda func: func

        def tool(self, *args, **kwargs):
            return lambda func: func

    modules = {
        "requests": types.SimpleNamespace(),
        "psutil": types.SimpleNamespace(cpu_percent=lambda interval=0: 0, virtual_memory=lambda: types.SimpleNamespace(percent=0)),
        "pandas": types.SimpleNamespace(read_csv=lambda path: None),
        "guitarpro": types.SimpleNamespace(parse=lambda path: None),
        "PIL": types.ModuleType("PIL"),
        "PIL.Image": types.SimpleNamespace(open=lambda path: None),
        "mcp": types.ModuleType("mcp"),
        "mcp.server": types.ModuleType("mcp.server"),
        "mcp.server.fastmcp": types.SimpleNamespace(FastMCP=FakeMCP),
        "starlette": types.ModuleType("starlette"),
        "starlette.requests": types.SimpleNamespace(Request=object),
        "starlette.responses": types.SimpleNamespace(JSONResponse=dict),
    }
    for name, module in modules.items():
        sys.modules.setdefault(name, module)

    spec = importlib.util.spec_from_file_location("mq_mcp_server_phase12_test", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_observation(**overrides):
    payload = {
        "schema_version": "memory-observation.v1",
        "producer": "mq-mcp",
        "repo": "mq-mcp",
        "observation_type": "review_signal",
        "title": "Repeated review warning",
        "summary": "Review found the same class of missing contract.",
        "evidence": [
            {
                "source": "review_repo",
                "quote": "Missing safety metadata in the tool contract.",
                "location": "mq-mcp/server.py:10",
            }
        ],
        "confidence": "medium",
    }
    payload.update(overrides)
    return payload


def _valid_feedback(**overrides):
    payload = {
        "schema_version": "feedback-signal.v1",
        "producer": "mq-mcp",
        "repo": "mq-mcp",
        "feedback_type": "recommendation_quality",
        "target": "review recommendation",
        "signal": "positive",
        "summary": "The recommendation matched an existing release blocker.",
        "evidence": ["release gate reported the same blocker"],
        "confidence": "medium",
    }
    payload.update(overrides)
    return payload


def test_phase12_schemas_are_loaded_from_schema_files():
    phase12 = _load_phase12()

    observation_schema = json.loads((ROOT / "schemas" / "memory-observation.v1.schema.json").read_text(encoding="utf-8"))
    feedback_schema = json.loads((ROOT / "schemas" / "feedback-signal.v1.schema.json").read_text(encoding="utf-8"))

    assert phase12.MEMORY_OBSERVATION_SCHEMA == observation_schema
    assert phase12.FEEDBACK_SIGNAL_SCHEMA == feedback_schema
    assert observation_schema["additionalProperties"] is False
    assert feedback_schema["additionalProperties"] is False


def test_validate_memory_observation_accepts_contract_shape():
    phase12 = _load_phase12()

    cleaned = phase12.validate_memory_observation(_valid_observation())

    assert cleaned["schema_version"] == "memory-observation.v1"
    assert cleaned["producer"] == "mq-mcp"
    assert cleaned["evidence"][0]["location"] == "mq-mcp/server.py:10"


def test_validate_memory_observation_rejects_missing_unknown_and_bad_producer():
    phase12 = _load_phase12()

    missing = _valid_observation()
    missing.pop("summary")
    with pytest.raises(ValueError, match="missing required"):
        phase12.validate_memory_observation(missing)

    with pytest.raises(ValueError, match="unknown field"):
        phase12.validate_memory_observation(_valid_observation(extra="nope"))

    with pytest.raises(ValueError, match="producer"):
        phase12.validate_memory_observation(_valid_observation(producer="mq-agent"))


def test_validate_feedback_signal_accepts_contract_shape():
    phase12 = _load_phase12()

    cleaned = phase12.validate_feedback_signal(_valid_feedback())

    assert cleaned["schema_version"] == "feedback-signal.v1"
    assert cleaned["feedback_type"] == "recommendation_quality"
    assert cleaned["signal"] == "positive"


def test_validate_feedback_signal_rejects_invalid_signal_and_empty_evidence():
    phase12 = _load_phase12()

    with pytest.raises(ValueError, match="unsupported signal"):
        phase12.validate_feedback_signal(_valid_feedback(signal="maybe"))

    with pytest.raises(ValueError, match="evidence"):
        phase12.validate_feedback_signal(_valid_feedback(evidence=[]))


def test_signal_payloads_redact_likely_secrets():
    phase12 = _load_phase12()

    cleaned = phase12.validate_feedback_signal(
        _valid_feedback(evidence=["OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789"])
    )

    assert "sk-" not in cleaned["evidence"][0]
    assert "<redacted>" in cleaned["evidence"][0]


def test_observation_from_review_finding_maps_architecture_review_signal():
    phase12 = _load_phase12()
    finding = SimpleNamespace(
        severity="ARCHITECTURE",
        location="docs/RUNTIME_CONTRACT.md:12",
        body="Architecture boundary should stay in mq-agent.",
    )

    observation = phase12.observation_from_review_finding(finding, repo="mq-mcp")

    assert observation["observation_type"] == "architecture_recommendation"
    assert observation["evidence"][0]["source"] == "review_engine.severity_engine"
    assert observation["evidence"][0]["location"] == "docs/RUNTIME_CONTRACT.md:12"


def test_recommendation_feedback_signal_builds_valid_payload():
    phase12 = _load_phase12()

    signal = phase12.recommendation_feedback_signal(
        repo="mq-mcp",
        target="review recommendation",
        signal="neutral",
        summary="The recommendation needs more evidence before promotion.",
        evidence=["review finding lacked a concrete file reference"],
        confidence="low",
    )

    assert signal["feedback_type"] == "recommendation_quality"
    assert signal["confidence"] == "low"


def test_repeated_bug_class_observation_builds_valid_payload():
    phase12 = _load_phase12()

    observation = phase12.repeated_bug_class_observation(
        repo="mq-mcp",
        bug_class="missing safety metadata",
        summary="The same safety metadata gap appeared in multiple review findings.",
        evidence=[
            {
                "source": "review_repo",
                "quote": "Missing safety metadata in tool contract.",
                "location": "docs/tool_contracts.json",
            },
            {
                "source": "review_repo",
                "quote": "Missing safety metadata in safety docs.",
                "location": "docs/TOOL_SAFETY.md",
            },
        ],
        confidence="high",
    )

    assert observation["observation_type"] == "repeated_bug_class"
    assert observation["title"] == "Repeated bug class: missing safety metadata"
    assert observation["confidence"] == "high"


def test_anti_pattern_observation_builds_valid_payload():
    phase12 = _load_phase12()

    observation = phase12.anti_pattern_observation(
        repo="mq-mcp",
        pattern_name="duplicated ownership",
        summary="Review evidence shows runtime code taking ownership of orchestration decisions.",
        evidence=[
            {
                "source": "review_diff",
                "quote": "mq-mcp should not orchestrate mq-agent workflows.",
                "location": "mq-mcp/server.py:42",
            }
        ],
    )

    assert observation["observation_type"] == "anti_pattern"
    assert observation["title"] == "Anti-pattern: duplicated ownership"


def test_architecture_recommendation_feedback_signal_builds_valid_payload():
    phase12 = _load_phase12()

    signal = phase12.architecture_recommendation_feedback_signal(
        repo="mq-mcp",
        target="docs/RUNTIME_CONTRACT.md boundary recommendation",
        signal="positive",
        summary="The recommendation matches the documented mq-agent boundary.",
        evidence=["docs/RUNTIME_CONTRACT.md says mq-agent owns orchestration"],
    )

    assert signal["feedback_type"] == "recommendation_quality"
    assert signal["target"] == "docs/RUNTIME_CONTRACT.md boundary recommendation"
    assert signal["signal"] == "positive"


def test_phase12_tools_are_registered_in_server_and_contracts():
    tool_names = {
        "phase12_review_observation",
        "phase12_repeated_bug_observation",
        "phase12_anti_pattern_observation",
        "phase12_architecture_feedback",
    }

    assert tool_names <= _mcp_tool_names()

    contracts = {
        item["name"]: item
        for item in json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))["tools"]
    }
    for name in tool_names:
        assert contracts[name]["class"] == "A"
        assert contracts[name]["write"] is False
        assert contracts[name]["subprocess"] is False


def test_phase12_server_tool_builds_review_observation_payload():
    server = _load_server_with_stubbed_dependencies()

    payload = server.phase12_review_observation(
        severity="WARNING",
        location="mq-mcp/server.py:1",
        body="Repeated review finding should become an observation.",
        repo="mq-mcp",
    )

    assert payload["schema_version"] == "memory-observation.v1"
    assert payload["producer"] == "mq-mcp"
    assert payload["observation_type"] == "repeated_bug_class"
    assert payload["evidence"][0]["location"] == "mq-mcp/server.py:1"
