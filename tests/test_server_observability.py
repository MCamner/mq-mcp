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
    assert payload["tool_count"] == 130
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


# ── the ingress gate, driven through the HTTP bridge ────────────────────────
#
# The bridge is covered above for what it refuses: non-loopback hosts, a
# rebinding Origin, a missing Host. What it does when a call is allowed
# through was untested — no test drove a tool with a payload over it, so the
# ingress decision and the vault write were only ever exercised by calling the
# reducer or going through `mcp.call_tool` in-process.
#
# That leaves the path a real mq-agent takes uncovered end to end: JSON body ->
# loopback guard -> `mcp.call_tool` -> reducer -> file on disk. Recovered from
# concurrent work that asserted this against the earlier single-argument
# `runtime_fingerprint`; rewritten for `producer` and the decisions the writer
# actually records.


def _tool_req(payload: dict, *, host: str | None = "127.0.0.1:8765"):
    """A Host-carrying request for a named tool, with a JSON body."""
    name = "brain_record_review"
    request = _req(host=host, path=f"/tools/{name}")
    request.path_params = {"name": name}

    async def _json() -> dict:
        return payload

    request.json = _json
    return request


def _review(**extra) -> dict:
    return {
        "source": "repo-signal:mq-agent",
        "finding_count": 1,
        "top_risks": [],
        "suggested_next_steps": [],
        **extra,
    }


def _identity(commit: str = "a" * 40, **extra) -> dict:
    return {
        "schema": "mq.runtime-identity.v1",
        "component": "mq-agent",
        "version": "1.28.0",
        "commit": commit,
        "install_type": "editable",
        "identity_quality": "verified",
        **extra,
    }


def _written(vault: Path) -> str:
    created = list((vault / "reviews").glob("*.md"))
    assert len(created) == 1, f"expected one review, found {len(created)}"
    return created[0].read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_a_caller_that_supplies_no_producer_still_writes(server, monkeypatch, tmp_path):
    """Absence is not contradiction: the review is written, and says so."""
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))

    response = await server.call_http_tool(_tool_req(_review()))
    result = json.loads(json.loads(response.body)[0]["text"])

    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept_with_warning"
    assert "producer-identity-missing" in result["ingress"]["reasons"]
    assert "ingress_decision: accept_with_warning" in _written(tmp_path)


@pytest.mark.anyio
async def test_both_halves_supplied_is_a_plain_accept_over_the_bridge(
    server, monkeypatch, tmp_path
):
    """The whole point of the gate, over the transport a real caller uses.

    Both halves, because that is what `signal --brain` sends: its own identity,
    and what it observed about the process taking the write. Either one alone
    still writes, but leaves the other named as a reason.
    """
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    commit = "b" * 40
    receiver = {
        "component": "mq-mcp",
        # What this process actually is. A receiver observation is a claim
        # about the process taking the write, so it is checked against it.
        "running": server._runtime_identity.identity(),
        "findings": [],
    }

    response = await server.call_http_tool(
        _tool_req(_review(producer=_identity(commit), receiver_observation=receiver))
    )
    result = json.loads(json.loads(response.body)[0]["text"])

    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept"
    assert result["ingress"]["reasons"] == []

    content = _written(tmp_path)
    assert "producer_component: mq-agent" in content
    assert f"producer_commit: {commit}" in content
    assert "producer_identity_quality: verified" in content


@pytest.mark.anyio
async def test_a_producer_without_a_receiver_still_writes_and_names_the_gap(
    server, monkeypatch, tmp_path
):
    """Half an observation is degraded, not refused — and the half that was
    supplied still reaches the frontmatter."""
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    commit = "d" * 40

    response = await server.call_http_tool(_tool_req(_review(producer=_identity(commit))))
    result = json.loads(json.loads(response.body)[0]["text"])

    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept_with_warning"
    assert result["ingress"]["reasons"] == ["receiver-observation-missing"]
    assert f"producer_commit: {commit}" in _written(tmp_path)


@pytest.mark.anyio
async def test_a_receiver_observation_naming_another_commit_is_refused(
    server, monkeypatch, tmp_path
):
    """A claim about this process, checked against this process.

    The caller says the receiver is running some other commit. That is not a
    mismatch between two sources — it is the record contradicting the process
    that holds it, and the frozen rule is that a self-contradiction refuses.
    """
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    elsewhere = dict(server._runtime_identity.identity(), commit="e" * 40)

    response = await server.call_http_tool(
        _tool_req(_review(
            producer=_identity(),
            receiver_observation={"component": "mq-mcp", "running": elsewhere, "findings": []},
        ))
    )
    result = json.loads(json.loads(response.body)[0]["text"])

    assert result["ok"] is False
    assert result["ingress"]["decision"] == "refuse"
    assert "receiver-running-commit-mismatch" in result["ingress"]["reasons"]
    assert not (tmp_path / "reviews").exists()


@pytest.mark.anyio
async def test_a_self_contradicting_producer_writes_nothing(server, monkeypatch, tmp_path):
    """`verified` against a commit that is not a commit. Refused, and no file.

    The refusal has to be observable at this boundary too: a caller that reads
    only the HTTP response must be able to tell a refusal from a write, and the
    vault must not be left holding evidence the gate rejected.
    """
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))

    response = await server.call_http_tool(
        _tool_req(_review(producer=_identity("not-a-sha")))
    )
    result = json.loads(json.loads(response.body)[0]["text"])

    assert result["ok"] is False
    assert result["ingress"]["decision"] == "refuse"
    assert "producer-identity-invalid" in result["ingress"]["reasons"]
    assert "producer-identity-invalid" in result["error"]
    assert not (tmp_path / "reviews").exists(), "a refused review left a file behind"


@pytest.mark.anyio
async def test_the_loopback_guard_runs_before_the_vault_is_touched(
    server, monkeypatch, tmp_path
):
    """Order matters: a rejected host must not reach the writer at all."""
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))

    response = await server.call_http_tool(
        _tool_req(_review(producer=_identity()), host="evil.example.com")
    )

    assert response.status_code != 200
    assert not (tmp_path / "reviews").exists()
