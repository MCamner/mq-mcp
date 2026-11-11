"""Bounded, read-only diagnostics for the optional CodeGraph integration."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path


def probe_daemon(root: Path) -> dict[str, object]:
    """Read CodeGraph's protocol-1 hello; a socket file alone proves nothing."""
    path = str(root / ".codegraph" / "daemon.sock")
    try:
        lock = json.loads((root / ".codegraph" / "daemon.pid").read_text())
        if isinstance(lock, dict) and isinstance(lock.get("socketPath"), str):
            path = lock["socketPath"]
    except (OSError, ValueError):
        pass
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            deadline = time.monotonic() + 1
            client.settimeout(1)
            client.connect(path)
            data = b""
            while b"\n" not in data and len(data) < 4096:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                client.settimeout(remaining)
                chunk = client.recv(4096 - len(data))
                if not chunk:
                    break
                data += chunk
            hello = json.loads(data.split(b"\n", 1)[0])
            if (not isinstance(hello, dict) or hello.get("protocol") != 1
                    or not isinstance(hello.get("codegraph"), str) or not hello["codegraph"]):
                raise ValueError("invalid daemon hello")
            return {"status": "ok", "version": hello["codegraph"], "detail": "Daemon answered."}
    except PermissionError:
        return {"status": "unknown", "detail": "Cannot confirm daemon: socket access denied.",
                "action": "Run mq-mcp doctor outside the sandbox with access to the project socket."}
    except (OSError, ValueError, UnicodeError):
        return {"status": "warning", "detail": "Daemon did not return a valid CodeGraph hello.",
                "action": "Open an agent with CodeGraph MCP enabled, retry doctor, then inspect .codegraph/daemon.log. An idle daemon may have stopped normally."}


def check_codegraph(root: Path) -> dict[str, object]:
    """Report optional health without starting daemons or changing the index."""
    executable = shutil.which("codegraph")
    if executable is None:
        return {"status": "skip", "detail": "CodeGraph CLI not found on PATH.",
                "action": "Install CodeGraph if this optional integration is wanted."}
    result: dict[str, object] = {"status": "warning", "version": None, "index_version": None}
    try:
        version = subprocess.run([executable, "--version"], cwd=root, capture_output=True,
                                 text=True, timeout=5, check=False)
        if version.returncode != 0 or not version.stdout.strip():
            raise ValueError("version command failed")
        result["version"] = version.stdout.strip()
        response = subprocess.run([executable, "status", "--json"], cwd=root,
                                  capture_output=True, text=True, timeout=5, check=False)
        if response.returncode != 0:
            raise ValueError("status command failed")
        data = json.loads(response.stdout)
        if not isinstance(data, dict) or not isinstance(data.get("initialized"), bool):
            raise ValueError("unsupported status JSON")
        if not data["initialized"]:
            return {**result, "index_status": "missing", "detail": "Project is not indexed.",
                    "action": "Run codegraph init in the project root if indexing is wanted."}
        index = data.get("index")
        changes = data.get("pendingChanges")
        if not isinstance(index, dict) or not isinstance(changes, dict):
            raise ValueError("unsupported index status JSON")
        result["index_version"] = index.get("builtWithVersion")
        if index.get("reindexRecommended") or index.get("state") != "complete" or data.get("worktreeMismatch"):
            result.update(index_status="rebuild", detail="Index needs a rebuild.",
                          action="Run codegraph index in the project root.")
        elif not all(type(changes.get(key)) is int and changes[key] >= 0
                     for key in ("added", "modified", "removed")):
            raise ValueError("unsupported pending changes JSON")
        elif any(changes.values()) or index.get("pendingRefs", 0):
            result.update(index_status="stale", detail="Index has pending file changes.",
                          action="Run codegraph sync in the project root.")
        else:
            result.update(status="ok", index_status="current", detail="Index is current.")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {**result, "detail": "Cannot confirm CodeGraph version/index (command failed, timed out or returned unsupported JSON).",
                "action": "Run codegraph --version and codegraph status --json in the project root; check CLI installation and permissions."}

    daemon = probe_daemon(root)
    result["daemon"] = daemon
    if daemon["status"] == "ok" and daemon["version"] != result["version"]:
        daemon.update(status="warning", detail="Daemon version differs from the CLI.",
                      action="Restart agents using CodeGraph to load the installed version.")
    if daemon["status"] != "ok":
        result["status"] = "warning"
        result["action"] = " ".join(filter(None, [result.get("action"), daemon.get("action")]))
    return result
