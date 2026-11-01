"""mqlaunch tools: a timeout is reported as a timeout, not as a failure.

mq-agent issue #438: `mqlaunch selftest` takes about two minutes, the tool gave
it 15 s, and the timeout came back as `exit 1 (failures)` — indistinguishable
from a failing selftest. No real mqlaunch runs here; subprocess.run is faked.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server_mqlaunch_timeout", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _timing_out(calls):
    def run(cmd, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
    return run


def _finishing(rc, calls):
    def run(cmd, **kwargs):
        calls.append(kwargs.get("timeout"))
        return subprocess.CompletedProcess(cmd, rc, stdout="[PASS] done\n", stderr="")
    return run


def test_timeout_returns_124_not_1(server, monkeypatch):
    monkeypatch.setattr(server.subprocess, "run", _timing_out([]))
    output, rc = server._run_mqlaunch("doctor", timeout=3)
    assert rc == 124
    assert "timed out after 3s" in output


def test_selftest_gets_room_for_its_real_runtime(server, monkeypatch):
    calls: list = []
    monkeypatch.setattr(server.subprocess, "run", _finishing(0, calls))
    assert server.run_mqlaunch_selftest().startswith("mqlaunch selftest [exit 0 (all pass)]")
    assert calls == [server.MQLAUNCH_SELFTEST_TIMEOUT]
    # Measured at ~126 s on 2026-11-01; the limit must clear that with margin.
    assert server.MQLAUNCH_SELFTEST_TIMEOUT >= 240


@pytest.mark.parametrize("tool", ["run_mqlaunch_doctor", "run_mqlaunch_selftest", "run_mqlaunch_release_check"])
def test_timeout_is_labelled_timed_out(server, monkeypatch, tool):
    monkeypatch.setattr(server.subprocess, "run", _timing_out([]))
    header = getattr(server, tool)().splitlines()[0]
    assert header.endswith("[exit 124 (timed out)]")


def test_real_failure_keeps_its_exit_code(server, monkeypatch):
    monkeypatch.setattr(server.subprocess, "run", _finishing(1, []))
    assert server.run_mqlaunch_selftest().startswith("mqlaunch selftest [exit 1 (failures)]")
