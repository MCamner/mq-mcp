"""
Review Context Evidence Loader — mq-mcp review engine

Decides whether a persisted repo-context artifact may be used to ground a
review, and reports what was verified. Implements ADR-008.

Canonical artifact:

  generated/architecture/architecture_map.json   schema: architecture_map.v1

The builder-internal map at review_engine/context/architecture_map.json is not
review evidence and must not be loaded through here.

Failure is split by kind, following the ingress rule in
docs/KNOWLEDGE_CONTRACT.md — a mismatch is a warning, a self-contradiction is a
refusal:

  VERIFIED   identity checks out, current, covers the repo
  STALE      identity checks out, but older than the freshness window
  INVALID    the artifact is not what it claims to be — nothing is used
  MISSING    no artifact — review runs without architecture context

STALE is usable. Refusing an artifact for age discards the entries it still
gets right and does nothing about the ones it never had. What must never
happen is context presented as more current or complete than it is, so every
result carries provenance lines for the operator.

The loader is pure: it reads the artifact and walks the repo, and writes
nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ARCHITECTURE_MAP_SCHEMA = "architecture_map.v1"

VERIFIED = "verified"
STALE = "stale"
INVALID = "invalid"
MISSING = "missing"

#: How old the underlying scan may be before the artifact degrades to STALE.
MAX_AGE = timedelta(hours=24)

#: Clocks disagree. Beyond this, a future timestamp is a contradiction.
FUTURE_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class ReviewContextResult:
    """What the loader verified, and what review may do with it."""

    status: str
    reasons: list[str] = field(default_factory=list)
    repo_name: str = ""
    generated_at: datetime | None = None
    age_hours: float | None = None
    entry_count: int = 0
    scanned_count: int = 0
    missing_files: list[str] = field(default_factory=list)
    _files: dict[str, dict] = field(default_factory=dict, repr=False)

    @property
    def usable(self) -> bool:
        """Whether the artifact may ground a review at all."""
        return self.status in (VERIFIED, STALE)

    def role_for(self, relative_path: str) -> str:
        """Architecture role for a file, or "" when there is nothing to say.

        Empty is not a fallback to a weaker source. It means this artifact has
        no verified role for that file.
        """
        if not self.usable:
            return ""
        entry = self._files.get(relative_path.replace("\\", "/"))
        role = entry.get("role", "") if isinstance(entry, dict) else ""
        return role if isinstance(role, str) and role != "unknown" else ""

    def entry_for(self, relative_path: str) -> dict:
        """Full verified entry for a file, or {}."""
        if not self.usable:
            return {}
        entry = self._files.get(relative_path.replace("\\", "/"))
        return dict(entry) if isinstance(entry, dict) else {}

    def provenance_lines(self) -> list[str]:
        """Operator-readable account of the context this review was given.

        Never includes absolute paths — the artifact's location is a machine
        detail, and review output is written to durable memory.
        """
        if not self.usable:
            reason = ", ".join(self.reasons) or "unknown"
            return ["Context", "  status       unavailable", f"  reason       {reason}"]

        lines = [
            "Context",
            f"  source       {ARCHITECTURE_MAP_SCHEMA}",
            f"  repo         {self.repo_name}",
        ]
        if self.generated_at is not None:
            lines.append(f"  generated_at {self.generated_at.isoformat()}")
        if self.age_hours is not None:
            lines.append(f"  age          {self.age_hours:.0f}h")
        lines.append(f"  coverage     {self.entry_count}/{self.scanned_count} files")
        lines.append(f"  status       {self.status}")
        if self.reasons:
            lines.append(f"  limits       {', '.join(self.reasons)}")
        return lines


def repo_identity(repo_root: Path) -> str:
    """Return the repo's declared name, falling back to the directory name.

    The directory is not the repo: a git worktree's directory differs from the
    repo it belongs to. .mq/repo-contract.json carries a committed,
    worktree-stable identity. A missing or unusable contract falls back rather
    than failing the caller.
    """
    try:
        contract = json.loads(
            (repo_root / ".mq" / "repo-contract.json").read_text(encoding="utf-8")
        )
        name = contract["repo"]
        if isinstance(name, str) and name.strip():
            return name
    except Exception:
        pass
    return repo_root.name


def _refused(status: str, *reasons: str) -> ReviewContextResult:
    return ReviewContextResult(status=status, reasons=list(reasons))


def _within_repo(relative_path: str) -> bool:
    """Whether a declared path stays inside the repo it claims to describe."""
    if not isinstance(relative_path, str) or not relative_path:
        return False
    candidate = Path(relative_path.replace("\\", "/"))
    if candidate.is_absolute():
        return False
    return ".." not in candidate.parts


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_review_context(
    artifact_path: Path,
    *,
    repo_root: Path,
    expected_repo: str,
    now: datetime | None = None,
    max_age: timedelta = MAX_AGE,
    future_skew: timedelta = FUTURE_SKEW,
) -> ReviewContextResult:
    """Load and verify a persisted architecture_map.v1 artifact.

    Args:
        artifact_path:  Path to the canonical artifact.
        repo_root:      Repo the review targets. Used to check containment,
                        which entries still have files, and coverage.
        expected_repo:  Repo name the artifact must declare.
        now:            Injected for determinism. Defaults to UTC now.
        max_age:        Beyond this the artifact degrades to STALE.
        future_skew:    Tolerance before a future timestamp is a contradiction.

    Never raises on bad input. Every failure is a status and a reason.
    """
    now = now or datetime.now(timezone.utc)

    if not artifact_path.exists():
        return _refused(MISSING, "artifact-missing")

    try:
        raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _refused(INVALID, "unparseable")

    if not isinstance(raw, dict):
        return _refused(INVALID, "not-an-object")

    if raw.get("schema") != ARCHITECTURE_MAP_SCHEMA:
        return _refused(INVALID, "schema-mismatch")

    repo_name = raw.get("repo_name")
    if not isinstance(repo_name, str) or repo_name != expected_repo:
        return _refused(INVALID, "repo-mismatch")

    generated_at = _parse_timestamp(raw.get("generated_at"))
    if generated_at is None:
        return _refused(INVALID, "generated-at-unparseable")
    if generated_at - now > future_skew:
        return _refused(INVALID, "generated-at-in-the-future")

    files = raw.get("files")
    if not isinstance(files, dict):
        return _refused(INVALID, "files-malformed")
    if not all(isinstance(entry, dict) for entry in files.values()):
        return _refused(INVALID, "files-malformed")
    if not all(_within_repo(rel) for rel in files):
        return _refused(INVALID, "path-escapes-repo")

    # Identity holds. Everything below narrows reach, it does not refuse.
    reasons: list[str] = []

    age = now - generated_at
    age_hours = max(age.total_seconds(), 0.0) / 3600
    status = VERIFIED
    if age > max_age:
        status = STALE
        reasons.append("stale")

    present = {rel: entry for rel, entry in files.items() if (repo_root / rel).exists()}
    missing_files = sorted(set(files) - set(present))
    if missing_files:
        reasons.append("entries-without-files")

    scanned_count = _scanned_count(repo_root)
    if scanned_count > len(present):
        reasons.append("partial-coverage")

    return ReviewContextResult(
        status=status,
        reasons=reasons,
        repo_name=repo_name,
        generated_at=generated_at,
        age_hours=age_hours,
        entry_count=len(present),
        scanned_count=scanned_count,
        missing_files=missing_files,
        _files=present,
    )


def _scanned_count(repo_root: Path) -> int:
    """How many files the builder would map, so coverage is measurable."""
    try:
        from review_engine.repo_context_builder import scan_architecture_map

        return len(scan_architecture_map(repo_root))
    except Exception:
        return 0
