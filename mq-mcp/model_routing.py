"""Validated read-only bridge from mq-mcp to mq-agent model routing."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
TOOLS = {
    "mq_route_inspect",
    "mq_route_shadow",
    "mq_context_pack",
    "mq_route_verify",
    "mq_route_report",
}


class AgentBridgeError(RuntimeError):
    """A redacted, machine-readable mq-agent bridge failure."""

    def __init__(self, code: str, status: str = "FAIL") -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(payload: Any, schema_path: Path) -> list[str]:
    validator = Draft202012Validator(_load_schema(schema_path))
    return sorted(error.json_path or "$" for error in validator.iter_errors(payload))


def _agent_home() -> Path:
    return Path(os.environ.get("MQ_AGENT_HOME", Path.home() / "mq-agent")).expanduser()


def _envelope(
    tool: str,
    status: str,
    data: dict[str, Any] | None,
    error_code: str | None = None,
) -> dict[str, Any]:
    if tool not in TOOLS:
        raise ValueError(f"unknown route tool: {tool}")
    result = {
        "schema": "mq.route-tool-result.v1",
        "tool": tool,
        "status": status,
        "data": data,
        "error_code": error_code,
    }
    errors = _validate(result, SCHEMAS / "mq_route_tool_result.schema.json")
    if errors:
        raise ValueError(f"invalid route tool envelope: {', '.join(errors)}")
    return result


def _run_agent_json(args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    home = _agent_home()
    if not home.is_dir():
        raise AgentBridgeError("mq-agent-unavailable", "UNAVAILABLE")
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
        raise AgentBridgeError("uv-unavailable", "UNAVAILABLE") from exc
    except subprocess.TimeoutExpired as exc:
        raise AgentBridgeError("mq-agent-timeout", "UNAVAILABLE") from exc
    if result.returncode != 0:
        raise AgentBridgeError("mq-agent-failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AgentBridgeError("invalid-json") from exc
    if not isinstance(payload, dict):
        raise AgentBridgeError("invalid-output")
    return payload


def _bridge_result(tool: str, args: list[str], *, timeout: int = 60) -> dict[str, Any]:
    try:
        data = _run_agent_json(args, timeout=timeout)
    except AgentBridgeError as exc:
        return _envelope(tool, exc.status, None, exc.code)
    return _envelope(tool, "PASS", data)


def route_inspect(task: str, *, authoritative_agent: str = "codex") -> dict[str, Any]:
    """Return mq-agent's deterministic routing recommendation."""
    tool = "mq_route_inspect"
    result = _bridge_result(
        tool,
        ["route", "inspect", task, "--agent", authoritative_agent, "--json"],
    )
    if result["status"] != "PASS":
        return result
    decision_schema = _agent_home() / "schemas" / "model_route_decision.schema.json"
    if not decision_schema.exists():
        return _envelope(tool, "UNAVAILABLE", None, "route-contract-unavailable")
    errors = _validate(result["data"], decision_schema)
    return result if not errors else _envelope(tool, "FAIL", None, "contract-invalid")


def route_shadow(
    task: str,
    *,
    authoritative_agent: str = "codex",
    timeout: int = 30,
) -> dict[str, Any]:
    """Request an advisory shadow candidate without accepting or storing it."""
    tool = "mq_route_shadow"
    try:
        data = _run_agent_json(
            [
                "route",
                "shadow",
                task,
                "--agent",
                authoritative_agent,
                "--timeout",
                str(timeout),
                "--json",
            ],
            timeout=timeout + 10,
        )
    except AgentBridgeError as exc:
        return _envelope(tool, exc.status, None, exc.code)

    decision_schema = _agent_home() / "schemas" / "model_route_decision.schema.json"
    outcome_schema = _agent_home() / "schemas" / "model_route_outcome.schema.json"
    if not decision_schema.exists() or not outcome_schema.exists():
        return _envelope(tool, "UNAVAILABLE", None, "route-contract-unavailable")
    if set(data) != {"decision", "candidate", "outcome"}:
        return _envelope(tool, "FAIL", None, "contract-invalid")
    if _validate(data.get("decision"), decision_schema) or _validate(
        data.get("outcome"), outcome_schema
    ):
        return _envelope(tool, "FAIL", None, "contract-invalid")
    candidate = data.get("candidate")
    if candidate is not None and _validate(candidate, SCHEMAS / "mq_route_candidate.schema.json"):
        return _envelope(tool, "FAIL", None, "contract-invalid")

    try:
        verification_status = str(data["outcome"]["verification"]["status"])
        escalation_reason = data["outcome"].get("escalation_reason")
    except (KeyError, TypeError, AttributeError):
        return _envelope(tool, "FAIL", None, "contract-invalid")
    status = {
        "PASS": "PASS",
        "SKIPPED": "WARN",
        "FAIL": "FAIL",
        "UNAVAILABLE": "UNAVAILABLE",
    }.get(verification_status, "FAIL")
    error_code = str(escalation_reason) if escalation_reason else None
    return _envelope(tool, status, data, error_code)


def context_pack(task: str, *, repo: str = "", target: str = "both") -> dict[str, Any]:
    """Return a task-scoped context pack on stdout without writing a file."""
    args = ["context", "pack", task, "--target", target, "--json"]
    if repo:
        args.extend(["--repo", repo])
    result = _bridge_result("mq_context_pack", args)
    if result["status"] != "PASS":
        return result
    data = result["data"]
    required = {"task", "target", "relevant_repos", "cards", "exclusions"}
    if not isinstance(data, dict) or not required <= set(data):
        return _envelope("mq_context_pack", "FAIL", None, "contract-invalid")
    return result


def route_verify(
    decision: dict[str, Any],
    candidate: dict[str, Any],
    *,
    agent_home: Path | None = None,
) -> dict[str, Any]:
    """Validate untrusted candidate data without executing or persisting it."""
    tool = "mq_route_verify"
    home = agent_home or _agent_home()
    decision_schema = home / "schemas" / "model_route_decision.schema.json"
    if not decision_schema.exists():
        return _envelope(tool, "UNAVAILABLE", None, "route-contract-unavailable")

    errors: list[str] = []
    checks: list[str] = []
    if _validate(decision, decision_schema):
        errors.append("decision-schema-invalid")
    else:
        checks.append("decision-schema")
    if _validate(candidate, SCHEMAS / "mq_route_candidate.schema.json"):
        errors.append("candidate-schema-invalid")
    else:
        checks.append("candidate-schema")
    if not errors and candidate.get("task_class") == decision.get("task_class"):
        checks.append("task-class-match")
    elif "candidate-schema-invalid" not in errors and "decision-schema-invalid" not in errors:
        errors.append("task-class-mismatch")

    verification = {
        "schema": "mq.route-verification.v1",
        "verification": {"status": "FAIL" if errors else "PASS", "checks": checks},
        "escalation_required": bool(errors),
        "errors": errors,
    }
    internal_errors = _validate(verification, SCHEMAS / "mq_route_verification.schema.json")
    if internal_errors:
        return _envelope(tool, "FAIL", None, "verification-contract-invalid")
    return _envelope(tool, "FAIL" if errors else "PASS", verification, "verification-failed" if errors else None)


def route_report(source: str = "") -> dict[str, Any]:
    """Return mq-agent's read-only aggregate routing report."""
    args = ["route", "report", "--json"]
    if source:
        args.extend(["--source", source])
    result = _bridge_result("mq_route_report", args)
    if result["status"] != "PASS":
        return result
    data = result["data"]
    required = {
        "schema",
        "total_records",
        "valid_outcomes",
        "attempted",
        "verified",
        "accepted_by_agent",
        "accepted_by_operator",
        "escalated",
    }
    if not isinstance(data, dict) or not required <= set(data):
        return _envelope("mq_route_report", "FAIL", None, "contract-invalid")
    return result
