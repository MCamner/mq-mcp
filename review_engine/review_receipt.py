"""Content-bound receipts for mq-mcp reviews.

A receipt proves which source snapshot a review result belongs to. HEAD alone
is insufficient because reviews routinely run against dirty working trees.
The subject snapshot therefore includes the exact bytes in review scope and the
current git commit.

Receipt generation is read-only. It snapshots before and after the review and
refuses to issue a bound receipt when the subject changed while the review was
running.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCHEMA = "mq.review-receipt.v1"
HASH_ALGORITHM = "sha256"
REVIEWABLE_EXTENSIONS = {".py", ".sh", ".md", ".json"}
IGNORED_REPO_PARTS = {"__pycache__", ".venv", "node_modules", ".git"}


def _git(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _digest_bytes(data: bytes) -> str:
    return f"{HASH_ALGORITHM}:{hashlib.sha256(data).hexdigest()}"


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return _digest_bytes(raw)


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    try:
        if not path.exists() or not path.is_file():
            return {"path": rel, "state": "missing", "sha256": None}
        return {
            "path": rel,
            "state": "present",
            "sha256": _digest_bytes(path.read_bytes()),
        }
    except OSError:
        return {"path": rel, "state": "unreadable", "sha256": None}


def _safe_path(root: Path, relative_path: str) -> Path:
    base = root.resolve()
    target = (base / relative_path).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"path escapes review root: {relative_path}") from exc
    return target


def _diff_paths(root: Path) -> list[Path]:
    raw = _git(root, "diff", "--name-only", "HEAD")
    names = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    return [
        _safe_path(root, name)
        for name in names
        if Path(name).suffix.lower() in REVIEWABLE_EXTENSIONS
    ]


def _repo_python_paths(root: Path) -> list[Path]:
    base = root.resolve()
    return sorted(
        (
            path
            for path in base.rglob("*.py")
            if not any(
                part in IGNORED_REPO_PARTS or part.startswith(".")
                for part in path.parts[len(base.parts):]
            )
        ),
        key=lambda path: path.relative_to(base).as_posix(),
    )


def _scope(root: Path, kind: str, relative_path: str | None) -> dict[str, Any]:
    base = root.resolve()
    if kind == "file":
        if not relative_path:
            raise ValueError("file receipt requires relative_path")
        paths = [_safe_path(base, relative_path)]
    elif kind == "diff":
        paths = _diff_paths(base)
    elif kind == "repo":
        paths = _repo_python_paths(base)
    else:
        raise ValueError(f"unsupported review kind: {kind}")

    files = [_file_record(base, path) for path in paths]
    scope: dict[str, Any] = {
        "type": kind,
        "file_count": len(files),
        "files": files,
    }
    if kind == "file":
        scope["path"] = relative_path
    return scope


def capture_subject(
    root: Path,
    *,
    kind: str,
    relative_path: str | None = None,
) -> dict[str, Any]:
    """Capture the exact local source state relevant to a review."""
    base = root.resolve()
    commit = _git(base, "rev-parse", "--verify", "HEAD")
    branch = _git(base, "branch", "--show-current")
    dirty_raw = _git(base, "status", "--porcelain")
    scope = _scope(base, kind, relative_path)
    fingerprint_input = {
        "repo": base.name,
        "commit": commit,
        "branch": branch or None,
        "scope": scope,
    }
    return {
        "repo": base.name,
        "commit": commit,
        "branch": branch or None,
        "worktree_clean": None if dirty_raw is None else not bool(dirty_raw),
        "scope": scope,
        "snapshot_sha256": _canonical_digest(fingerprint_input),
    }


def result_digest(result: Any) -> str:
    """Hash the actual review result without assuming a transport shape."""
    if isinstance(result, (dict, list)):
        return _canonical_digest(result)
    return _digest_bytes(str(result).encode("utf-8"))


def _receipt_id(core: dict[str, Any]) -> str:
    return _canonical_digest(core)


def verify_receipt_id(receipt: dict[str, Any]) -> bool:
    """Verify the receipt's own content address without touching the subject."""
    receipt_id = receipt.get("receipt_id")
    core = {key: value for key, value in receipt.items() if key != "receipt_id"}
    return isinstance(receipt_id, str) and receipt_id == _receipt_id(core)


def issue_receipt(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    result: Any,
    kind: str,
    mode: str,
    producer: dict[str, Any],
    started_at: str,
    completed_at: str | None = None,
) -> dict[str, Any]:
    """Build an immutable receipt from two observations of one review subject."""
    finished = completed_at or datetime.now(UTC).isoformat()
    unchanged = before.get("snapshot_sha256") == after.get("snapshot_sha256")

    if not before.get("commit"):
        status = "REFUSED"
        reason = "subject-commit-unavailable"
    elif not unchanged:
        status = "REFUSED"
        reason = "subject-changed-during-review"
    else:
        status = "ISSUED"
        reason = "exact-subject-snapshot-stable"

    core: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "started_at": started_at,
        "completed_at": finished,
        "subject": before,
        "stability": {
            "before": before.get("snapshot_sha256"),
            "after": after.get("snapshot_sha256"),
            "unchanged": unchanged,
        },
        "producer": producer,
        "review": {
            "kind": kind,
            "mode": mode,
            "result_sha256": result_digest(result),
            "result": result,
        },
    }
    return {"receipt_id": _receipt_id(core), **core}


def run_receipted_review(
    *,
    root: Path,
    kind: str,
    mode: str,
    run: Callable[[], Any],
    producer: dict[str, Any],
    relative_path: str | None = None,
) -> dict[str, Any]:
    """Run a review between two subject snapshots and return its receipt."""
    started_at = datetime.now(UTC).isoformat()
    before = capture_subject(root, kind=kind, relative_path=relative_path)
    result = run()
    after = capture_subject(root, kind=kind, relative_path=relative_path)
    return issue_receipt(
        before=before,
        after=after,
        result=result,
        kind=kind,
        mode=mode,
        producer=producer,
        started_at=started_at,
    )
