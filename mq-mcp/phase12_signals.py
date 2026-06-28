"""Phase 12D signal payloads for mq-mcp.

This module only builds and validates payloads that mqobsidian-owned schemas
can later consume. It does not write durable memory, promote candidates, score
repo health, or orchestrate workflows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

OBSERVATION_SCHEMA_VERSION = "memory-observation.v1"
FEEDBACK_SCHEMA_VERSION = "feedback-signal.v1"
PRODUCER = "mq-mcp"

OBSERVATION_TYPES = {
    "review_signal",
    "repeated_bug_class",
    "anti_pattern",
    "architecture_recommendation",
}
FEEDBACK_TYPES = {
    "recommendation_quality",
    "review_pattern_reuse",
    "promotion_candidate",
}
CONFIDENCE = {"high", "medium", "low"}
FEEDBACK_SIGNALS = {"positive", "neutral", "negative"}

MEMORY_OBSERVATION_SCHEMA: dict[str, Any] = {}
FEEDBACK_SIGNAL_SCHEMA: dict[str, Any] = {}

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)(bearer)\s+[A-Za-z0-9._\-]+"),
]


def _load_schema(filename: str) -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / filename
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


MEMORY_OBSERVATION_SCHEMA = _load_schema("memory-observation.v1.schema.json")
FEEDBACK_SIGNAL_SCHEMA = _load_schema("feedback-signal.v1.schema.json")


def redact_secrets(value: Any) -> Any:
    """Redact likely secrets from signal payload strings, lists, and dicts."""
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("<redacted>", redacted)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_secrets(item) for key, item in value.items()}
    return value


def validate_memory_observation(payload: Any) -> dict[str, Any]:
    """Return a cleaned `memory-observation.v1` payload or raise ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("memory observation must be a JSON object")

    required = {
        "schema_version",
        "producer",
        "repo",
        "observation_type",
        "title",
        "summary",
        "evidence",
        "confidence",
    }
    _reject_missing_or_unknown(payload, required, "memory observation")

    cleaned = {
        "schema_version": _required_string(payload, "schema_version"),
        "producer": _required_string(payload, "producer"),
        "repo": _required_string(payload, "repo"),
        "observation_type": _required_string(payload, "observation_type"),
        "title": _required_string(payload, "title"),
        "summary": _required_string(payload, "summary"),
        "evidence": _clean_observation_evidence(payload["evidence"]),
        "confidence": _required_string(payload, "confidence"),
    }

    if cleaned["schema_version"] != OBSERVATION_SCHEMA_VERSION:
        raise ValueError("unsupported memory observation schema_version")
    if cleaned["producer"] != PRODUCER:
        raise ValueError("memory observation producer must be mq-mcp")
    if cleaned["observation_type"] not in OBSERVATION_TYPES:
        raise ValueError(f"unsupported observation_type: {cleaned['observation_type']}")
    if cleaned["confidence"] not in CONFIDENCE:
        raise ValueError(f"unsupported confidence: {cleaned['confidence']}")
    return redact_secrets(cleaned)


def validate_feedback_signal(payload: Any) -> dict[str, Any]:
    """Return a cleaned `feedback-signal.v1` payload or raise ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("feedback signal must be a JSON object")

    required = {
        "schema_version",
        "producer",
        "repo",
        "feedback_type",
        "target",
        "signal",
        "summary",
        "evidence",
        "confidence",
    }
    _reject_missing_or_unknown(payload, required, "feedback signal")

    evidence = payload["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("feedback signal evidence must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in evidence):
        raise ValueError("feedback signal evidence entries must be non-empty strings")

    cleaned = {
        "schema_version": _required_string(payload, "schema_version"),
        "producer": _required_string(payload, "producer"),
        "repo": _required_string(payload, "repo"),
        "feedback_type": _required_string(payload, "feedback_type"),
        "target": _required_string(payload, "target"),
        "signal": _required_string(payload, "signal"),
        "summary": _required_string(payload, "summary"),
        "evidence": [item.strip() for item in evidence],
        "confidence": _required_string(payload, "confidence"),
    }

    if cleaned["schema_version"] != FEEDBACK_SCHEMA_VERSION:
        raise ValueError("unsupported feedback signal schema_version")
    if cleaned["producer"] != PRODUCER:
        raise ValueError("feedback signal producer must be mq-mcp")
    if cleaned["feedback_type"] not in FEEDBACK_TYPES:
        raise ValueError(f"unsupported feedback_type: {cleaned['feedback_type']}")
    if cleaned["signal"] not in FEEDBACK_SIGNALS:
        raise ValueError(f"unsupported signal: {cleaned['signal']}")
    if cleaned["confidence"] not in CONFIDENCE:
        raise ValueError(f"unsupported confidence: {cleaned['confidence']}")
    return redact_secrets(cleaned)


def observation_from_review_finding(finding: Any, *, repo: str = "mq-mcp") -> dict[str, Any]:
    """Map a parsed review finding to a `memory-observation.v1` payload."""
    severity = str(getattr(getattr(finding, "severity", ""), "value", getattr(finding, "severity", ""))).upper()
    location = str(getattr(finding, "location", "")).strip()
    body = str(getattr(finding, "body", "")).strip()
    if not location or not body:
        raise ValueError("review finding must include location and body")

    observation_type = _observation_type_for(severity, body)
    return validate_memory_observation(
        {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "producer": PRODUCER,
            "repo": repo,
            "observation_type": observation_type,
            "title": f"{severity or 'REVIEW'} finding at {location}",
            "summary": body,
            "evidence": [
                {
                    "source": "review_engine.severity_engine",
                    "quote": body,
                    "location": location,
                }
            ],
            "confidence": "medium",
        }
    )


def recommendation_feedback_signal(
    *,
    repo: str,
    target: str,
    signal: str,
    summary: str,
    evidence: list[str],
    confidence: str = "medium",
) -> dict[str, Any]:
    """Build validated recommendation-quality feedback for Phase 12D."""
    return validate_feedback_signal(
        {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "producer": PRODUCER,
            "repo": repo,
            "feedback_type": "recommendation_quality",
            "target": target,
            "signal": signal,
            "summary": summary,
            "evidence": evidence,
            "confidence": confidence,
        }
    )


def repeated_bug_class_observation(
    *,
    repo: str,
    bug_class: str,
    summary: str,
    evidence: list[dict[str, str]],
    confidence: str = "medium",
) -> dict[str, Any]:
    """Build a repeated bug-class observation from review evidence."""
    return validate_memory_observation(
        {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "producer": PRODUCER,
            "repo": repo,
            "observation_type": "repeated_bug_class",
            "title": f"Repeated bug class: {bug_class}",
            "summary": summary,
            "evidence": evidence,
            "confidence": confidence,
        }
    )


def anti_pattern_observation(
    *,
    repo: str,
    pattern_name: str,
    summary: str,
    evidence: list[dict[str, str]],
    confidence: str = "medium",
) -> dict[str, Any]:
    """Build an anti-pattern observation from review evidence."""
    return validate_memory_observation(
        {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "producer": PRODUCER,
            "repo": repo,
            "observation_type": "anti_pattern",
            "title": f"Anti-pattern: {pattern_name}",
            "summary": summary,
            "evidence": evidence,
            "confidence": confidence,
        }
    )


def architecture_recommendation_feedback_signal(
    *,
    repo: str,
    target: str,
    summary: str,
    evidence: list[str],
    signal: str = "neutral",
    confidence: str = "medium",
) -> dict[str, Any]:
    """Build feedback for architecture recommendation quality."""
    return validate_feedback_signal(
        {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "producer": PRODUCER,
            "repo": repo,
            "feedback_type": "recommendation_quality",
            "target": target,
            "signal": signal,
            "summary": summary,
            "evidence": evidence,
            "confidence": confidence,
        }
    )


def _observation_type_for(severity: str, body: str) -> str:
    text = body.lower()
    if severity in {"ARCHITECTURE", "RISK"} or "architecture" in text:
        return "architecture_recommendation"
    if "anti-pattern" in text or "antipattern" in text:
        return "anti_pattern"
    if "repeated" in text or "same issue" in text:
        return "repeated_bug_class"
    return "review_signal"


def _reject_missing_or_unknown(payload: dict[str, Any], required: set[str], label: str) -> None:
    keys = set(payload)
    missing = sorted(required - keys)
    unknown = sorted(keys - required)
    if missing:
        raise ValueError(f"{label} missing required field(s): {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{label} has unknown field(s): {', '.join(unknown)}")


def _required_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload[field_name]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _clean_observation_evidence(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("memory observation evidence must be a non-empty list")

    cleaned: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("memory observation evidence entries must be objects")
        required = {"source", "quote"}
        allowed = required | {"location"}
        keys = set(item)
        missing = sorted(required - keys)
        unknown = sorted(keys - allowed)
        if missing:
            raise ValueError(f"memory observation evidence missing field(s): {', '.join(missing)}")
        if unknown:
            raise ValueError(f"memory observation evidence has unknown field(s): {', '.join(unknown)}")
        entry = {
            "source": _required_string(item, "source"),
            "quote": _required_string(item, "quote"),
        }
        location = item.get("location")
        if location is not None:
            if not isinstance(location, str):
                raise ValueError("memory observation evidence location must be a string")
            entry["location"] = location.strip()
        cleaned.append(entry)
    return cleaned
