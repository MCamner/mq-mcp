"""Ollama structured-output provider for mq-mcp.

Wraps the local Ollama HTTP API (http://localhost:11434) with:
- JSON schema validation on every response
- Confidence and evidence field enforcement
- Hard exclusions: no release decisions, no destructive approvals, no secret handling
- Graceful fallback when Ollama is unavailable or returns invalid output

This module is imported by server.py tools (ollama_learn_extract,
ollama_learn_status). It does not register MCP tools itself.

Safety class: B — network read from local Ollama; no persistent writes.
The caller (server.py) owns storage gates and mq-mcp contract enforcement.
"""

from __future__ import annotations

import json
import time
from typing import Any

import requests

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_TIMEOUT = 60  # seconds


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------


def health() -> dict[str, Any]:
    """Return Ollama health status. Never raises — returns error dict on failure."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        resp.raise_for_status()
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        return {"status": "ok", "endpoint": OLLAMA_BASE, "models": models}
    except requests.ConnectionError:
        return {"status": "unavailable", "endpoint": OLLAMA_BASE, "error": "connection refused"}
    except Exception as exc:
        return {"status": "error", "endpoint": OLLAMA_BASE, "error": str(exc)}


def list_models() -> list[str]:
    """Return installed Ollama model names. Raises OllamaUnavailableError if down."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except requests.ConnectionError as exc:
        raise OllamaUnavailableError("Ollama is not running") from exc


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------


def chat_json(
    model: str,
    prompt: str,
    system: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Send a prompt to Ollama and parse the response as JSON.

    Returns the parsed dict. Raises OllamaValidationError if response is
    not valid JSON or if Ollama returns an error status.
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    if system:
        payload["system"] = system

    try:
        resp = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.ConnectionError as exc:
        raise OllamaUnavailableError("Ollama is not running") from exc
    except requests.HTTPError as exc:
        raise OllamaValidationError(f"Ollama returned HTTP {exc.response.status_code}") from exc

    raw = resp.json().get("response", "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaValidationError(f"Ollama returned non-JSON: {raw[:200]}") from exc


# ---------------------------------------------------------------------------
# Learn extraction
# ---------------------------------------------------------------------------

_LEARN_SYSTEM = (
    "You are an engineering lesson extractor. "
    "You read mq-mcp review findings and extract structured lessons. "
    "You output JSON only. You never approve releases, destructive commands, or security decisions. "
    "You never invent file paths or commands not present in the input."
)

_LEARN_PROMPT_TEMPLATE = """Extract engineering lessons from these review findings.

FINDINGS:
{findings}

Return a JSON array. Each item must have exactly these fields:
- pattern_name: short-kebab-case-slug
- pattern_type: one of architecture, docs, integration, release, safety, testing, unknown
- summary: one sentence — what was learned
- evidence: array of strings — specific quotes from the findings above
- recommended_action: one sentence — what to do next time
- confidence: high, medium, or low
- should_store: true if confidence is high or medium, false if low

Return only the JSON array. No prose. No markdown.
"""


def _validate_learn_item(item: Any) -> list[str]:
    """Return list of validation errors for a learn extraction item."""
    errors = []
    required = ["pattern_name", "pattern_type", "summary", "evidence",
                "recommended_action", "confidence", "should_store"]
    for field in required:
        if field not in item:
            errors.append(f"missing field: {field}")

    valid_types = {"architecture", "docs", "integration", "release", "safety", "testing", "unknown"}
    if item.get("pattern_type") not in valid_types:
        errors.append(f"invalid pattern_type: {item.get('pattern_type')}")

    if item.get("confidence") not in {"high", "medium", "low"}:
        errors.append(f"invalid confidence: {item.get('confidence')}")

    if not isinstance(item.get("evidence"), list) or len(item.get("evidence", [])) == 0:
        errors.append("evidence must be a non-empty array")

    return errors


def extract_learn_items(
    findings: str,
    model: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Extract structured learn candidates from review findings text.

    Returns a dict with keys:
      candidates   — list of valid items with should_store=True
      rejected     — list of items that failed validation or have should_store=False
      errors       — list of string errors encountered
      model        — model used
      elapsed_ms   — time taken
    """
    started = time.time()
    prompt = _LEARN_PROMPT_TEMPLATE.format(findings=findings[:8000])

    try:
        raw = chat_json(model, prompt, system=_LEARN_SYSTEM, timeout=timeout)
    except OllamaUnavailableError as exc:
        return {"candidates": [], "rejected": [], "errors": [str(exc)], "model": model, "elapsed_ms": 0}
    except OllamaValidationError as exc:
        return {"candidates": [], "rejected": [], "errors": [str(exc)], "model": model, "elapsed_ms": 0}

    items = raw if isinstance(raw, list) else raw.get("items", [raw])

    candidates = []
    rejected = []
    errors = []

    for item in items:
        if not isinstance(item, dict):
            errors.append(f"non-dict item: {str(item)[:80]}")
            continue
        validation_errors = _validate_learn_item(item)
        if validation_errors:
            rejected.append({"item": item, "errors": validation_errors})
        elif not item.get("should_store", False):
            rejected.append({"item": item, "reason": "should_store=false"})
        else:
            candidates.append(item)

    return {
        "candidates": candidates,
        "rejected": rejected,
        "errors": errors,
        "model": model,
        "elapsed_ms": round((time.time() - started) * 1000),
    }


# ---------------------------------------------------------------------------
# Review summary
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = (
    "You are a code review summariser. "
    "You read mq-mcp review findings and produce a compact structured summary. "
    "You output JSON only conforming to review_summary.v1 schema. "
    "You never approve releases or destructive actions."
)

_SUMMARY_PROMPT_TEMPLATE = """Summarise these review findings as review_summary.v1 JSON.

SOURCE: {source}
FINDING COUNT: {finding_count}

FINDINGS:
{findings}

Return a JSON object with these fields:
- schema_version: "review_summary.v1"
- source: "{source}"
- confidence: high, medium, or low
- finding_count: {finding_count}
- severity_breakdown: object with severity label counts
- top_risks: array of strings (top risk findings, plain language)
- suggested_next_steps: array of strings (concrete actions — no release approvals)
- learn_candidates: array of pattern_name strings worth extracting to learn memory

Return only the JSON object. No prose. No markdown.
"""


def review_summary(
    findings: str,
    source: str,
    model: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Produce a review_summary.v1 JSON object from review findings text.

    Returns the validated summary dict, or a dict with an 'error' key on failure.
    """
    finding_count = findings.count("\n[") + findings.count("\n---")
    prompt = _SUMMARY_PROMPT_TEMPLATE.format(
        source=source,
        finding_count=max(finding_count, 1),
        findings=findings[:8000],
    )

    try:
        result = chat_json(model, prompt, system=_SUMMARY_SYSTEM, timeout=timeout)
    except (OllamaUnavailableError, OllamaValidationError) as exc:
        return {"error": str(exc), "source": source}

    result.setdefault("schema_version", "review_summary.v1")
    result.setdefault("source", source)
    return result
