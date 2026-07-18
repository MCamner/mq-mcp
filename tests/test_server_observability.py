import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _req(host: str | None = "127.0.0.1:8765", path: str = "/health"):
    """Minimal stand-in for a Starlette Request carrying a Host header."""
    headers = {} if host is None else {"host": host}
    return SimpleNamespace(headers=headers, url=SimpleNamespace(path=path))


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server_observability", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.anyio
async def test_health_endpoint_reports_version_and_tool_count(server):
    response = await server.health_check(_req())
    payload = json.loads(response.body)

    assert payload["status"] == "ok"
    assert payload["version"] == VERSION
    assert payload["tool_count"] == 125
    assert "elapsed_ms" in payload


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1:8765", "localhost:8765", "127.0.0.1", "[::1]:8765", "LOCALHOST:8765"],
)
def test_loopback_hosts_are_allowed(server, host):
    assert server._is_loopback_request(_req(host)) is True


@pytest.mark.parametrize(
    "host",
    ["evil.com", "attacker.example:8765", "192.168.1.10:8765", "", None],
)
def test_non_loopback_hosts_are_rejected(server, host):
    assert server._is_loopback_request(_req(host)) is False


@pytest.mark.anyio
async def test_call_http_tool_rejects_dns_rebinding_origin(server):
    """A DNS-rebinding page carries a foreign Host and must get a 403, not a tool call."""
    response = await server.call_http_tool(_req(host="evil.com", path="/tools/get_public_ip"))
    assert response.status_code == 403
    assert "loopback" in json.loads(response.body)["error"]


@pytest.mark.anyio
async def test_health_endpoint_rejects_foreign_host(server):
    response = await server.health_check(_req(host="evil.com"))
    assert response.status_code == 403


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
