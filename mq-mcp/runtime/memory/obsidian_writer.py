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
    """Write a code review summary to memory/reviews/.

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
    return _write("memory/reviews", filename, fm + f"# Review: {source}\n\n" + _body(*sections))


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


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-style frontmatter. Returns (fields, body_after_fm)."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    fm_text = content[4:end]
    body = content[end + 5:]
    fields: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for line in fm_text.splitlines():
        if line.startswith("  - ") and current_key and current_list is not None:
            current_list.append(line[4:])
        elif ":" in line:
            if current_key and current_list is not None:
                fields[current_key] = current_list
                current_list = None
            if ": " in line:
                k, _, v = line.partition(": ")
                v = v.strip().strip('"')
                fields[k.strip()] = v
                current_key = k.strip()
            else:
                current_key = line.rstrip(":").strip()
                current_list = []
                fields[current_key] = current_list
    if current_key and current_list is not None:
        fields[current_key] = current_list
    return fields, body


def _set_frontmatter_field(content: str, key: str, value: str) -> str:
    """Add or update a scalar field in YAML frontmatter. No-op if no frontmatter."""
    if not content.startswith("---\n"):
        return content
    end = content.find("\n---\n", 4)
    if end == -1:
        return content
    fm_lines = content[4:end].splitlines()
    body_after = content[end + 5:]
    updated = False
    new_lines = []
    for line in fm_lines:
        if line.startswith(f"{key}:"):
            new_lines.append(f"{key}: {value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}: {value}")
    return "---\n" + "\n".join(new_lines) + "\n---\n" + body_after


def _learning_source_path(slug_clean: str) -> tuple[Path, str] | None:
    """Find a learn note in the standard path, falling back to legacy root learn/."""
    candidates = [
        ("memory/learn", _vault() / "memory" / "learn" / f"{slug_clean}.md"),
        ("learn", _vault() / "learn" / f"{slug_clean}.md"),
    ]
    for prefix, path in candidates:
        if path.exists():
            return path, f"{prefix}/{slug_clean}.md"
    return None


def promote_learning(slug: str) -> dict[str, Any]:
    """Promote memory/learn/<slug>.md to memory/learn/verified/.

    1. Reads memory/learn/<slug>.md, with legacy learn/<slug>.md fallback
    2. Validates required frontmatter fields and body sections
    3. Writes memory/learn/verified/<timestamp>-<slug>.md with promoted_at + status: verified
    4. Marks original as status: promoted

    Returns {"ok": True, "path": "...", "source": "..."} or {"ok": False, "error": "..."}.
    """
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}

    slug_clean = slug.removeprefix("memory/learn/").removeprefix("learn/").removesuffix(".md")
    found = _learning_source_path(slug_clean)

    if found is None:
        return {"ok": False, "error": f"Not found: memory/learn/{slug_clean}.md or learn/{slug_clean}.md"}
    source_path, source_ref = found

    content = source_path.read_text(encoding="utf-8")
    fm_fields, body = _parse_frontmatter(content)

    missing_fields = [f for f in ("pattern_name", "pattern_type") if not fm_fields.get(f)]
    if missing_fields:
        return {"ok": False, "error": f"Missing required frontmatter: {', '.join(missing_fields)}"}

    body_lower = body.lower()
    missing_sections = [
        s for s in ("## summary", "## evidence", "## recommended action")
        if s not in body_lower
    ]
    if missing_sections:
        return {"ok": False, "error": f"Missing required sections: {', '.join(missing_sections)}"}

    now = _now_iso()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    promoted_filename = f"learn-{ts}-{slug_clean}.md"

    promoted_fm = dict(fm_fields)
    promoted_fm["status"] = "verified"
    promoted_fm["promoted_at"] = now
    promoted_fm["promoted_from"] = source_ref

    result = _write("memory/learn/verified", promoted_filename, _frontmatter(**promoted_fm) + body)
    if not result.get("ok"):
        return result

    updated = _set_frontmatter_field(content, "status", "promoted")
    source_path.write_text(updated, encoding="utf-8")

    return {"ok": True, "path": result["path"], "source": str(source_path), "slug": slug_clean}


def record_learning(
    pattern_name: str,
    pattern_type: str,
    summary: str,
    evidence: list[str],
    recommended_action: str,
    confidence: str = "medium",
) -> dict[str, Any]:
    """Write a learned pattern to memory/learn/.

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
    return _write("memory/learn", filename, fm + f"# Pattern: {pattern_name}\n\n" + _body(*sections))
