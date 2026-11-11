import json
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq-mcp"))
import codegraph_health as health


def status(**updates):
    data = dict(initialized=True, version="1.6.2", pendingChanges=dict(added=0, modified=0, removed=0),
                index=dict(builtWithVersion="1.6.2", state="complete", reindexRecommended=False),
                worktreeMismatch=None)
    data.update(updates)
    return data


def setup_cli(monkeypatch, data=None):
    monkeypatch.setattr(health.shutil, "which", lambda _: "/bin/codegraph")
    def run(args, **kwargs):
        assert kwargs["timeout"] == 5
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(args, 0, "1.6.2\n" if "--version" in args else json.dumps(data or status()), "")
    monkeypatch.setattr(health.subprocess, "run", run)
    monkeypatch.setattr(health, "probe_daemon", lambda _: dict(status="ok", version="1.6.2", detail="Daemon answered."))


def test_missing_cli_does_not_run_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(health.shutil, "which", lambda _: None)
    result = health.check_codegraph(tmp_path)
    assert result["status"] == "skip"
    assert "install" in result["action"].lower()


def test_healthy_index_and_daemon(monkeypatch, tmp_path):
    setup_cli(monkeypatch)
    result = health.check_codegraph(tmp_path)
    assert result["status"] == "ok"
    assert result["version"] == result["index_version"] == "1.6.2"
    assert result["daemon"]["status"] == "ok"


@pytest.mark.parametrize("updates,command", [
    ({"pendingChanges": {"added": 1, "modified": 0, "removed": 0}}, "codegraph sync"),
    ({"index": {"reindexRecommended": True, "state": "complete"}}, "codegraph index"),
    ({"index": {"state": "building"}}, "codegraph index"),
    ({"initialized": False}, "codegraph init"),
    ({"worktreeMismatch": {"expected": "other"}}, "codegraph index"),
])
def test_unhealthy_index_has_action(monkeypatch, tmp_path, updates, command):
    setup_cli(monkeypatch, status(**updates))
    result = health.check_codegraph(tmp_path)
    assert result["status"] == "warning"
    assert command in result["action"]


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("codegraph", 5), OSError("unavailable")])
def test_command_failure_is_reported(monkeypatch, tmp_path, failure):
    setup_cli(monkeypatch)
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(health.subprocess, "run", fail)
    assert health.check_codegraph(tmp_path)["status"] == "warning"


@pytest.mark.parametrize("output,returncode", [("not json", 0), ("[]", 0), ("{}", 2)])
def test_invalid_status_is_reported(monkeypatch, tmp_path, output, returncode):
    setup_cli(monkeypatch)
    monkeypatch.setattr(health.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, returncode, output, ""))
    assert health.check_codegraph(tmp_path)["status"] == "warning"


def test_socket_hello_uses_pidfile_path(monkeypatch, tmp_path):
    directory = tmp_path / ".codegraph"
    directory.mkdir()
    (directory / "daemon.pid").write_text(json.dumps({"socketPath": "/tmp/test-codegraph.sock"}))
    client = MagicMock()
    client.__enter__.return_value = client
    client.recv.side_effect = [b'{"codegraph":"1.', b'6.2","protocol":1,"pid":123}\n']
    monkeypatch.setattr(health.socket, "socket", lambda *args: client)
    result = health.probe_daemon(tmp_path)
    assert result["status"] == "ok"
    client.connect.assert_called_once_with("/tmp/test-codegraph.sock")


@pytest.mark.parametrize("error,expected", [(PermissionError(), "unknown"), (ConnectionRefusedError(), "warning"), (socket.timeout(), "warning")])
def test_socket_failures_are_not_healthy(monkeypatch, tmp_path, error, expected):
    client = MagicMock()
    client.__enter__.return_value = client
    client.connect.side_effect = error
    monkeypatch.setattr(health.socket, "socket", lambda *args: client)
    assert health.probe_daemon(tmp_path)["status"] == expected


def test_invalid_hello_is_not_healthy(monkeypatch, tmp_path):
    client = MagicMock()
    client.__enter__.return_value = client
    client.recv.return_value = b'{}\n'
    monkeypatch.setattr(health.socket, "socket", lambda *args: client)
    assert health.probe_daemon(tmp_path)["status"] == "warning"


def test_daemon_version_mismatch(monkeypatch, tmp_path):
    setup_cli(monkeypatch)
    monkeypatch.setattr(health, "probe_daemon", lambda _: dict(status="ok", version="1.5.0", detail="Daemon answered."))
    result = health.check_codegraph(tmp_path)
    assert result["status"] == "warning"
    assert "Restart" in result["action"]


def test_missing_freshness_fields_are_not_healthy(monkeypatch, tmp_path):
    setup_cli(monkeypatch, status(pendingChanges={}))
    assert health.check_codegraph(tmp_path)["status"] == "warning"


def test_pending_references_are_not_healthy(monkeypatch, tmp_path):
    data = status()
    data["index"]["pendingRefs"] = 2
    setup_cli(monkeypatch, data)
    assert health.check_codegraph(tmp_path)["index_status"] == "stale"


def test_inactive_daemon_retains_index_repair_action(monkeypatch, tmp_path):
    setup_cli(monkeypatch, status(pendingChanges={"added": 1, "modified": 0, "removed": 0}))
    monkeypatch.setattr(health, "probe_daemon", lambda _: {
        "status": "warning", "detail": "Not responding.", "action": "Open an agent."})
    result = health.check_codegraph(tmp_path)
    assert result["status"] == "warning"
    assert "codegraph sync" in result["action"]
    assert "Open an agent" in result["action"]
