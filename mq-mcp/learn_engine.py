"""Deterministic learning storage for mq-mcp.

The learning layer captures verified engineering lessons. It is intentionally
local-only and non-executing: lessons may inform future reviews, runbooks, and
agent guidance, but they must never mutate router policy, allowlists, or run
commands.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)(bearer)\s+[A-Za-z0-9._\-]+"),
]

_ALLOWED_SOURCES = {"codex", "claude", "mq-agent", "mq-hal", "manual", "review", "diff"}
_ALLOWED_RISKS = {"low", "medium", "high", "unknown"}
_PROMOTION_TARGETS = {"runbook", "agents-md", "claude-md", "architecture-memory"}


@dataclass
class LearningRecord:
    """A verified engineering lesson."""

    id: str
    repo: str
    source: str
    task: str
    lesson: str
    validation: list[str]
    problem: str = ""
    solution: str = ""
    files_touched: list[str] = field(default_factory=list)
    commands_used: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    risk: str = "unknown"
    promoted_to: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def learning_dir(repo_root: Path) -> Path:
    return repo_root / "learn_engine" / "memory"


def learning_store_path(repo_root: Path) -> Path:
    return learning_dir(repo_root) / "lessons.jsonl"


def redact_secrets(value: Any) -> Any:
    """Redact likely secrets from strings, lists, and dictionaries."""
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


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _next_id(repo_root: Path) -> str:
    existing = load_learnings(repo_root)
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    return f"learn_{ts}_{len(existing) + 1:04d}"


def make_learning(
    repo_root: Path,
    *,
    repo: str,
    source: str,
    task: str,
    lesson: str,
    validation: str | list[str],
    problem: str = "",
    solution: str = "",
    files_touched: str | list[str] | None = None,
    commands_used: str | list[str] | None = None,
    tags: str | list[str] | None = None,
    risk: str = "unknown",
) -> LearningRecord:
    source = source.strip().lower()
    risk = risk.strip().lower()
    if source not in _ALLOWED_SOURCES:
        raise ValueError(f"Unsupported learning source: {source}")
    if risk not in _ALLOWED_RISKS:
        raise ValueError(f"Unsupported risk value: {risk}")
    if not repo.strip():
        raise ValueError("repo is required")
    if not task.strip():
        raise ValueError("task is required")
    if not lesson.strip():
        raise ValueError("lesson is required")

    record = LearningRecord(
        id=_next_id(repo_root),
        repo=repo.strip(),
        source=source,
        task=task.strip(),
        lesson=lesson.strip(),
        validation=_as_list(validation),
        problem=problem.strip(),
        solution=solution.strip(),
        files_touched=_as_list(files_touched),
        commands_used=_as_list(commands_used),
        tags=_as_list(tags),
        risk=risk,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    return LearningRecord(**redact_secrets(record.to_dict()))


def record_learning(repo_root: Path, record: LearningRecord) -> dict[str, Any]:
    """Append a learning record to local JSONL storage."""
    path = learning_store_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.to_dict()
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        if path.exists()
        else json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"status": "ok", "id": record.id, "path": str(path)}


def load_learnings(repo_root: Path) -> list[dict[str, Any]]:
    path = learning_store_path(repo_root)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def get_learning(repo_root: Path, learning_id: str) -> dict[str, Any] | None:
    for record in load_learnings(repo_root):
        if record.get("id") == learning_id:
            return record
    return None


def search_learnings(repo_root: Path, query: str) -> list[dict[str, Any]]:
    q = query.lower().strip()
    if not q:
        return load_learnings(repo_root)
    matches = []
    for record in load_learnings(repo_root):
        haystack = json.dumps(record, ensure_ascii=False).lower()
        if q in haystack:
            matches.append(record)
    return matches


def summarize_learnings(repo_root: Path, limit: int = 20) -> str:
    records = load_learnings(repo_root)[-limit:]
    if not records:
        return "No learning records found."
    lines = ["# Learning summary", ""]
    for record in records:
        tags = ", ".join(record.get("tags") or []) or "no-tags"
        validation = "; ".join(record.get("validation") or []) or "not recorded"
        lines.append(f"- `{record.get('id')}` [{record.get('source')}/{record.get('risk')}] {record.get('task')}")
        lines.append(f"  - Lesson: {record.get('lesson')}")
        lines.append(f"  - Validation: {validation}")
        lines.append(f"  - Tags: {tags}")
    return "\n".join(lines)


def promotion_preview(repo_root: Path, learning_id: str, target: str) -> str:
    """Return a dry-run promotion block. This function never writes files."""
    target = target.strip().lower()
    if target not in _PROMOTION_TARGETS:
        raise ValueError(f"Unsupported promotion target: {target}")
    record = get_learning(repo_root, learning_id)
    if record is None:
        raise ValueError(f"Learning record not found: {learning_id}")

    target_path = {
        "runbook": "docs/RUNBOOK.md",
        "agents-md": "AGENTS.md",
        "claude-md": "CLAUDE.md",
        "architecture-memory": "architecture_memory/",
    }[target]

    return "\n".join(
        [
            "# Learning promotion preview",
            "",
            f"Target: `{target_path}`",
            f"Learning: `{record['id']}`",
            "",
            "## Proposed addition",
            "",
            f"### {record['task']}",
            "",
            f"- Source: {record['source']}",
            f"- Repo: {record['repo']}",
            f"- Risk: {record['risk']}",
            f"- Lesson: {record['lesson']}",
            f"- Validation: {'; '.join(record.get('validation') or [])}",
            "",
            "This is a dry-run preview. No files were changed.",
        ]
    )
