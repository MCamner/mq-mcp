"""Tests for quit_app: quit one macOS app by name, optionally force-quit it.

No real app is touched: osascript and os.kill are replaced with fakes that
model one running process. The fakes record every call so the tests can prove
the name never reaches AppleScript source text and that force only ever
signals the single pid System Events reported.
"""

import importlib.util
import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))

from bridget_safety import load_safety_map, needs_approval, tool_class


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server_quit_app", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeMac:
    """One running app; `obeys_quit` decides whether AppleScript quit works."""

    def __init__(self, name="Spotify", pid=4242, bundle="com.spotify.client", obeys_quit=True):
        self.name, self.pid, self.bundle = name, pid, bundle
        self.obeys_quit = obeys_quit
        self.alive = True
        self.calls: list[list[str]] = []
        self.signals: list[tuple[int, int]] = []

    def run(self, cmd, **_kwargs):
        self.calls.append(cmd)
        argv = cmd[cmd.index("--") + 1:] if "--" in cmd else []
        script = " ".join(cmd[1:cmd.index("--")] if "--" in cmd else cmd[1:])
        if "System Events" in script:
            out = f"{self.pid}\t{self.bundle}" if self.alive and argv == [self.name] else ""
            return subprocess.CompletedProcess(cmd, 0, out + "\n", "")
        if "to quit" in script:
            if self.obeys_quit:
                self.alive = False
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(f"unexpected command: {cmd}")

    def kill(self, pid, sig):
        if sig == 0:
            if not (self.alive and pid == self.pid):
                raise ProcessLookupError
            return
        self.signals.append((pid, sig))
        if pid == self.pid:
            self.alive = False


@pytest.fixture
def mac(server, monkeypatch):
    fake = FakeMac()
    monkeypatch.setattr(server.subprocess, "run", fake.run)
    monkeypatch.setattr(server.os, "kill", fake.kill)
    monkeypatch.setattr(server, "_QUIT_WAIT_SECONDS", 0.05)
    return fake


def test_quits_running_app_normally(server, mac):
    result = json.loads(server.quit_app("Spotify"))
    assert result["status"] == "quit"
    assert result["app_name"] == "Spotify"
    assert result["force"] is False
    assert mac.signals == []


def test_not_running_returns_not_running(server, mac):
    result = json.loads(server.quit_app("Notes"))
    assert result["status"] == "not_running"
    assert not any("to quit" in " ".join(c) for c in mac.calls)


def test_unresponsive_app_fails_without_force(server, mac):
    mac.obeys_quit = False
    result = json.loads(server.quit_app("Spotify"))
    assert result["status"] == "failed"
    assert mac.signals == []
    assert mac.alive


def test_force_kills_only_the_reported_pid(server, mac):
    mac.obeys_quit = False
    result = json.loads(server.quit_app("Spotify", force=True))
    assert result["status"] == "quit"
    assert result["force"] is True
    assert mac.signals == [(4242, signal.SIGKILL)]


def test_name_is_argv_never_script_text(server, mac):
    hostile = 'Spotify" to quit\ndo shell script "rm -rf ~'
    result = json.loads(server.quit_app(hostile))
    assert result["status"] in ("failed", "not_running")
    for cmd in mac.calls:
        script = " ".join(cmd[1:cmd.index("--")])
        assert "rm -rf" not in script


@pytest.mark.parametrize("name", ["", "   ", "/Applications/Safari.app", "a" * 200])
def test_invalid_names_rejected_before_any_subprocess(server, mac, name):
    result = json.loads(server.quit_app(name))
    assert result["status"] == "failed"
    assert mac.calls == []


@pytest.mark.parametrize("name", ["Finder", "Dock", "loginwindow", "SystemUIServer", "WindowServer"])
def test_system_processes_are_protected(server, mac, name):
    result = json.loads(server.quit_app(name, force=True))
    assert result["status"] == "failed"
    assert mac.calls == []
    assert mac.signals == []


def test_quit_app_is_class_d_and_gated_in_bridget():
    smap = load_safety_map()
    assert tool_class("quit_app", smap) == "D"
    assert needs_approval("quit_app", smap) is True
