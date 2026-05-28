import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server_observability", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.anyio
async def test_health_endpoint_reports_version_and_tool_count(server):
    response = await server.health_check(object())
    payload = json.loads(response.body)

    assert payload["status"] == "ok"
    assert payload["version"] == "1.9.0"
    assert payload["tool_count"] == 76
    assert "elapsed_ms" in payload


def test_redacted_env_hides_api_key(server, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    payload = server._redacted_env()

    assert payload["OPENAI_API_KEY"]["value"] == "<redacted>"
    assert "sk-test-secret" not in json.dumps(payload)


def test_contract_classes_are_exposed_as_safety_labels(server):
    assert server._contract_class_to_safety("A") == "read-only"
    assert server._contract_class_to_safety("B") == "read-only"
    assert server._contract_class_to_safety("C") == "write-capable"
    assert server._contract_class_to_safety("D") == "subprocess"


def test_enrich_tool_uses_caller_facing_safety_label(server):
    enriched = server._enrich_tool({"name": "review_diff"})
    assert enriched["safety_class"] == "read-only"
