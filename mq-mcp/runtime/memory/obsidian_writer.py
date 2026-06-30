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
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION_DECISION = "decision.v1"
SCHEMA_VERSION_REVIEW = "review.v1"
SCHEMA_VERSION_SESSION = "session.v1"
SCHEMA_VERSION_LEARN = "learn.v1"
SCHEMA_MEMORY_SCORE = "memory-score.v1"
SCHEMA_PROMOTION_EVENT = "promotion-event.v1"


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


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Low-level write
# ---------------------------------------------------------------------------


def _write(folder: str, filename: str, content: str) -> dict[str, Any]:
    target_dir = _vault() / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target)}


def _write_json(folder: str, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _write(folder, filename, json.dumps(payload, indent=2, sort_keys=True) + "\n")


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


def _load_observations() -> tuple[list[dict[str, Any]], list[str]]:
    observations_dir = _vault() / "memory" / "observations"
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    if not observations_dir.exists():
        return observations, [f"Not found: {observations_dir}"]

    for path in sorted(observations_dir.rglob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        for line_no, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.name}:{line_no}: invalid JSON: {exc.msg}")
                continue
            if record.get("schema") != "memory-observation.v1":
                errors.append(f"{path.name}:{line_no}: unsupported schema")
                continue
            if not record.get("id") or not record.get("timestamp"):
                errors.append(f"{path.name}:{line_no}: missing id or timestamp")
                continue
            observations.append(record)
    return observations, errors


def _memory_key(record: dict[str, Any]) -> str:
    key = str(record.get("proposed_memory_key") or "").strip()
    if key:
        return key
    title = str(record.get("title") or record.get("id") or "memory").strip()
    return _slug(title, max_len=80) or str(record["id"])


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _recency_factor(last_seen: str) -> float:
    seen_at = _parse_datetime(last_seen)
    if seen_at is None:
        return 0.25
    age_days = (datetime.now(timezone.utc) - seen_at).days
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.75
    if age_days <= 90:
        return 0.5
    return 0.25


def _source_count(records: list[dict[str, Any]]) -> int:
    sources: set[str] = set()
    for record in records:
        producer = str(record.get("producer") or "").strip()
        if producer:
            sources.add(producer)
        for evidence in record.get("evidence") or []:
            if isinstance(evidence, dict):
                source = str(evidence.get("source") or "").strip()
                if source:
                    sources.add(source)
    return len(sources)


def _needs_human_review(records: list[dict[str, Any]]) -> bool:
    risk_words = {
        "architecture",
        "boundary",
        "boundaries",
        "credential",
        "credentials",
        "delete",
        "deletion",
        "global",
        "public",
        "safety",
        "secret",
        "secrets",
        "write",
    }
    for record in records:
        category = str(record.get("category") or "").lower()
        if category in {"architecture", "decision"}:
            return True
        haystack = json.dumps(record, ensure_ascii=False).lower()
        if any(word in haystack for word in risk_words):
            return True
    return False


def _score_status(factors: dict[str, float], *, needs_review: bool, negative: int) -> str:
    if negative > 0:
        return "deprecated"
    if (
        factors["frequency"] >= 8
        and factors["confidence"] >= 0.75
        and factors["source_count"] >= 2
        and factors["usage_score"] > 0
        and not needs_review
    ):
        return "promoted"
    if (
        factors["frequency"] >= 3
        and factors["confidence"] >= 0.65
        and factors["source_count"] >= 1
    ):
        return "candidate"
    return "observed"


def _existing_score_status(memory_id: str) -> str | None:
    path = _vault() / "memory" / "scores" / f"{_slug(memory_id, max_len=80)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    status = payload.get("status")
    return status if isinstance(status, str) else None


def _build_memory_scores() -> tuple[list[dict[str, Any]], list[str]]:
    observations, errors = _load_observations()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in observations:
        grouped.setdefault(_memory_key(record), []).append(record)

    scores: list[dict[str, Any]] = []
    for memory_id, records in sorted(grouped.items()):
        timestamps = sorted(str(r.get("timestamp")) for r in records if r.get("timestamp"))
        confidences = [
            float(r.get("confidence"))
            for r in records
            if isinstance(r.get("confidence"), (int, float))
        ]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        factors = {
            "frequency": float(len(records)),
            "source_count": float(_source_count(records)),
            "confidence": round(confidence, 3),
            "recency": _recency_factor(timestamps[-1]) if timestamps else 0.25,
            "usage_score": 0.0,
            "manual_boost": 0.0,
        }
        feedback = {"positive": 0, "negative": 0}
        needs_review = _needs_human_review(records)
        score = (
            factors["frequency"]
            + factors["source_count"] * 2
            + factors["confidence"] * 4
            + factors["recency"]
            + factors["usage_score"]
            + factors["manual_boost"]
            - feedback["negative"] * 3
        )
        status = _score_status(factors, needs_review=needs_review, negative=feedback["negative"])
        first_seen = timestamps[0][:10] if timestamps else _today_iso()
        last_seen = timestamps[-1][:10] if timestamps else _today_iso()
        scores.append(
            {
                "schema": SCHEMA_MEMORY_SCORE,
                "memory_id": memory_id,
                "timestamp": _now_iso(),
                "status": status,
                "score": round(score, 3),
                "factors": factors,
                "observed_by": sorted(
                    {
                        str(record.get("producer"))
                        for record in records
                        if str(record.get("producer") or "").strip()
                    }
                ),
                "feedback": feedback,
                "first_seen": first_seen,
                "last_seen": last_seen,
            }
        )
    return scores, errors


def preview_memory_scores() -> dict[str, Any]:
    """Score real memory observations without writing mqobsidian files."""
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}
    scores, errors = _build_memory_scores()
    return {
        "ok": True,
        "vault": str(_vault()),
        "scores": scores,
        "errors": errors,
        "would_write": {
            "scores": "memory/scores/<memory_id>.json",
            "promotion_events": "memory/promotions/promotion-events.jsonl",
        },
    }


def apply_memory_scores() -> dict[str, Any]:
    """Score observations and write memory-score.v1 plus promotion-event.v1 audit."""
    preview = preview_memory_scores()
    if not preview.get("ok"):
        return preview

    score_paths: list[str] = []
    events: list[dict[str, Any]] = []
    for score in preview["scores"]:
        memory_id = str(score["memory_id"])
        previous = _existing_score_status(memory_id) or "observed"
        filename = f"{_slug(memory_id, max_len=80)}.json"
        result = _write_json("memory/scores", filename, score)
        score_paths.append(result["path"])
        if previous != score["status"]:
            events.append(
                {
                    "schema": SCHEMA_PROMOTION_EVENT,
                    "id": f"{_today_iso()}-{_slug(memory_id, max_len=60)}-{previous}-to-{score['status']}",
                    "timestamp": _now_iso(),
                    "producer": "mq-mcp/obsidian_writer",
                    "memory_id": memory_id,
                    "from": previous,
                    "to": score["status"],
                    "reason": "Policy scoring from real memory-observation.v1 records.",
                    "score": score["score"],
                    "evidence": {
                        "frequency": score["factors"]["frequency"],
                        "source_count": score["factors"]["source_count"],
                        "confidence": score["factors"]["confidence"],
                        "feedback": score["feedback"]["positive"] - score["feedback"]["negative"],
                    },
                }
            )

    events_path = _vault() / "memory" / "promotions" / "promotion-events.jsonl"
    if events:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, sort_keys=True) + "\n")

    return {
        "ok": True,
        "vault": str(_vault()),
        "scored": len(preview["scores"]),
        "score_paths": score_paths,
        "promotion_events": len(events),
        "promotion_events_path": str(events_path) if events else "",
        "errors": preview["errors"],
    }


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


def promote_learning(slug: str) -> dict[str, Any]:
    """Promote learn/<slug>.md to learn/verified/.

    1. Reads learn/<slug>.md
    2. Validates required frontmatter fields and body sections
    3. Writes learn/verified/<timestamp>-<slug>.md with promoted_at + status: verified
    4. Marks original as status: promoted

    Returns {"ok": True, "path": "...", "source": "..."} or {"ok": False, "error": "..."}.
    """
    if not vault_exists():
        return {"ok": False, "error": f"Vault not found: {_vault()}"}

    slug_clean = slug.removeprefix("learn/").removesuffix(".md")
    source_path = _vault() / "learn" / f"{slug_clean}.md"

    if not source_path.exists():
        return {"ok": False, "error": f"Not found: learn/{slug_clean}.md"}

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
    promoted_fm["promoted_from"] = f"learn/{slug_clean}.md"

    result = _write("learn/verified", promoted_filename, _frontmatter(**promoted_fm) + body)
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
