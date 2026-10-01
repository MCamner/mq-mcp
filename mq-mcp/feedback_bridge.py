"""Thin subprocess bridge from mq-mcp to mq-agent Feedback Engine.

mq-agent owns all feedback contracts, evidence, verdicts and candidates. This
module only delegates stable CLI calls and returns their JSON unchanged.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


class FeedbackBridgeError(RuntimeError):
    """Redacted failure from the mq-agent feedback bridge."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _agent_home() -> Path:
    return Path(os.environ.get("MQ_AGENT_HOME", Path.home() / "mq-agent")).expanduser()


def _run(args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    home = _agent_home()
    if not home.is_dir():
        raise FeedbackBridgeError("mq-agent-unavailable")
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
        raise FeedbackBridgeError("uv-unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise FeedbackBridgeError("mq-agent-timeout") from exc
    if result.returncode != 0:
        raise FeedbackBridgeError("mq-agent-feedback-failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FeedbackBridgeError("mq-agent-invalid-json") from exc
    if not isinstance(payload, dict):
        raise FeedbackBridgeError("mq-agent-invalid-output")
    return payload


def _safe_call(args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    try:
        return _run(args, timeout=timeout)
    except FeedbackBridgeError as exc:
        return {
            "schema": "mq.feedback-tool-error.v1",
            "status": "UNAVAILABLE",
            "error_code": exc.code,
        }


def status() -> dict[str, Any]:
    return _safe_call(["feedback", "status", "--json"])


def inspect(feedback_run_id: str) -> dict[str, Any]:
    return _safe_call(["feedback", "inspect", feedback_run_id, "--json"])


def compare(feedback_run_id: str) -> dict[str, Any]:
    # Deliberately no fixture/evaluator options: MCP comparison is observation
    # only. Evidence-changing F3 derivation remains an explicit mq-agent CLI act.
    return _safe_call(["feedback", "compare", feedback_run_id, "--json"])


def report(task_class: str = "", since: str = "") -> dict[str, Any]:
    args = ["feedback", "report", "--json"]
    if task_class:
        args.extend(["--task-class", task_class])
    if since:
        args.extend(["--since", since])
    return _safe_call(args)


def candidates() -> dict[str, Any]:
    return _safe_call(["feedback", "candidates", "--json"])


def run(
    task: str,
    *,
    repo: str,
    task_class: str = "repo-review",
    timeout_ms: int = 2000,
    max_context_bytes: int = 65536,
    max_sources: int = 64,
) -> dict[str, Any]:
    return _safe_call(
        [
            "feedback",
            "run",
            "--task",
            task,
            "--repo",
            repo,
            "--task-class",
            task_class,
            "--timeout-ms",
            str(max(1, timeout_ms)),
            "--max-context-bytes",
            str(max(1, max_context_bytes)),
            "--max-sources",
            str(max(1, max_sources)),
            "--json",
        ],
        timeout=max(30, int(timeout_ms / 1000) + 20),
    )
