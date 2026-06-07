"""Obsidian second-brain writer for mq-mcp.

Writes structured records to the local mqobsidian vault.
All writes are:
  - append-only to new date-stamped files
  - local-only (no sync, no push)
  - explicit (no automatic background writes)
  - schema-tagged in the frontmatter

Safety class: C — writes to local filesystem (vault only, no repo writes).
Caller must gate on user approval before calling record_* functions.

Vault path: MQ_OBSIDIAN_DIR env var, or ~/mqobsidian.
Contract:   mq-mcp/docs/KNOWLEDGE_CONTRACT.md
"""

from __future__ import annotations

import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION_DECISION = "decision.v1"
SCHEMA_VERSION_REVIEW = "review.v1"
SCHEMA_VERSION_SESSION = "session.v1"
SCHEMA_VERSION_LEARN = "learn.v1"


# ---------------------------------------------------------------------------
# Vault resolution
# ---------------------------------------------------------------------------


def _vault() -> Path:
    env = os.getenv("MQ_OBSIDIAN_DIR")
    return Path(env).expanduser().resolve() if env else Path.home() / "mqobsidian"


def vault_path() -> Path:
    return _vault()


def vault_exists() -> bool:
    return _vault().is_dir()


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------


def _slug(text: str, max_len: int = 40) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:max_len].rstrip("-")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Low-level write
# ---------------------------------------------------------------------------


def _write(folder: str, filename: str, content: str) -> dict[str, Any]:
    target_dir = _vault() / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target)}


def _frontmatter(**fields: Any) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _body(*sections: tuple[str, str]) -> str:
    """Build a markdown body from (heading, content) pairs. No indentation drift."""
    parts = []
    for heading, content in sections:
        parts.append(f"## {heading}\n\n{content}")
    return "\n\n".join(parts) + "\n"


def record_decision(
    title: str,
    context: str,
    decision: str,
    rationale: str,
    consequences: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Write an architecture decision record to decisions/.

    Returns {"ok": True, "path": "..."} or {"ok": False, "error": "..."}.
    """
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}

    tags = tags or []
    slug = _slug(title)
    filename = f"{_today()}-{slug}.md"
    fm = _frontmatter(
        schema_version=SCHEMA_VERSION_DECISION,
        written_by="mq-mcp/obsidian_writer",
        timestamp=_now_iso(),
        title=title,
        tags=tags,
    )
    sections = [("Context", context), ("Decision", decision), ("Rationale", rationale)]
    if consequences:
        sections.append(("Consequences", consequences))
    return _write("decisions", filename, fm + f"# {title}\n\n" + _body(*sections))


def record_review(
    source: str,
    finding_count: int,
    top_risks: list[str],
    suggested_next_steps: list[str],
    confidence: str = "medium",
    raw_summary: str = "",
) -> dict[str, Any]:
    """Write a code review summary to reviews/.

    Returns {"ok": True, "path": "..."} or {"ok": False, "error": "..."}.
    """
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}

    slug = _slug(source)
    filename = f"{_today()}-{slug}.md"
    fm = _frontmatter(
        schema_version=SCHEMA_VERSION_REVIEW,
        written_by="mq-mcp/obsidian_writer",
        timestamp=_now_iso(),
        source=source,
        finding_count=finding_count,
        confidence=confidence,
    )
    risks_md = "\n".join(f"- {r}" for r in top_risks) or "- none"
    steps_md = "\n".join(f"- {s}" for s in suggested_next_steps) or "- none"
    meta = f"**Findings:** {finding_count}  \n**Confidence:** {confidence}"
    sections = [("Summary", meta), ("Top risks", risks_md), ("Suggested next steps", steps_md)]
    if raw_summary:
        sections.append(("Full summary", raw_summary))
    return _write("reviews", filename, fm + f"# Review: {source}\n\n" + _body(*sections))


def record_session(
    title: str,
    summary: str,
    repos: list[str] | None = None,
    outcomes: list[str] | None = None,
    follow_ups: list[str] | None = None,
) -> dict[str, Any]:
    """Write a session note to sessions/.

    Returns {"ok": True, "path": "..."} or {"ok": False, "error": "..."}.
    """
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}

    repos = repos or []
    outcomes = outcomes or []
    follow_ups = follow_ups or []
    slug = _slug(title)
    filename = f"{_today()}-{slug}.md"
    fm = _frontmatter(
        schema_version=SCHEMA_VERSION_SESSION,
        written_by="mq-mcp/obsidian_writer",
        timestamp=_now_iso(),
        title=title,
        repos=repos,
    )
    repos_md = "\n".join(f"- {r}" for r in repos) or "- none"
    outcomes_md = "\n".join(f"- {o}" for o in outcomes) or "- none"
    follow_ups_md = "\n".join(f"- {f}" for f in follow_ups) or "- none"
    sections = [
        ("Summary", summary),
        ("Repos touched", repos_md),
        ("Outcomes", outcomes_md),
        ("Follow-ups", follow_ups_md),
    ]
    return _write("sessions", filename, fm + f"# {title}\n\n" + _body(*sections))


def record_learning(
    pattern_name: str,
    pattern_type: str,
    summary: str,
    evidence: list[str],
    recommended_action: str,
    confidence: str = "medium",
) -> dict[str, Any]:
    """Write a learned pattern to learn/.

    Overwrites existing file — patterns are updated, not duplicated.
    Returns {"ok": True, "path": "..."} or {"ok": False, ...}.
    """
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}

    slug = _slug(pattern_name)
    filename = f"{slug}.md"
    fm = _frontmatter(
        schema_version=SCHEMA_VERSION_LEARN,
        written_by="mq-mcp/obsidian_writer",
        timestamp=_now_iso(),
        pattern_name=pattern_name,
        pattern_type=pattern_type,
        confidence=confidence,
    )
    meta = f"**Type:** {pattern_type}  \n**Confidence:** {confidence}"
    evidence_md = "\n".join(f"- {e}" for e in evidence) or "- none"
    sections = [
        ("Overview", meta),
        ("Summary", summary),
        ("Evidence", evidence_md),
        ("Recommended action", recommended_action),
    ]
    return _write("learn", filename, fm + f"# Pattern: {pattern_name}\n\n" + _body(*sections))
