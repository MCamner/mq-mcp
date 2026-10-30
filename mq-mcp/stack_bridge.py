"""Thin subprocess bridge from mq-mcp to mq-agent's stack cockpit.

mq-agent owns the cockpit contract (mq_stack_cockpit.schema.json) and every
verdict in it. This module only delegates the fixed CLI call and returns its
JSON unchanged.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


class StackBridgeError(RuntimeError):
    """Redacted failure from the mq-agent stack bridge."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _agent_home() -> Path:
    return Path(os.environ.get("MQ_AGENT_HOME", Path.home() / "mq-agent")).expanduser()


def _run(args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    home = _agent_home()
    if not home.is_dir():
        raise StackBridgeError("mq-agent-unavailable")
    command = ["uv", "--project", str(home), "run", "mq-agent", *args]
    try:
        result = subprocess.run(
            command,
            cwd=home,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise StackBridgeError("uv-unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise StackBridgeError("mq-agent-timeout") from exc
    if result.returncode != 0:
        raise StackBridgeError("mq-agent-stack-failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise StackBridgeError("mq-agent-invalid-json") from exc
    if not isinstance(payload, dict):
        raise StackBridgeError("mq-agent-invalid-output")
    return payload


def cockpit() -> dict[str, Any]:
    try:
        return _run(["stack", "cockpit", "--json"])
    except StackBridgeError as exc:
        return {
            "schema": "mq.stack-tool-error.v1",
            "status": "UNAVAILABLE",
            "error_code": exc.code,
        }
