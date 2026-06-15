#!/usr/bin/env python3
"""post_commit_learn.py — auto-extract a learn candidate from the last commit.

Run by the git post-commit hook (in the background). It feeds the just-made
commit's diff to the local mq-learn Ollama model and writes any grounded,
medium/high-confidence candidate to a *pending inbox* — never to the curated
learn store. Nothing lands in lessons.jsonl without explicit human/agent
promotion, so an auto hook cannot poison the store with hallucinated lessons.

Design choices (deliberate):
  * No-op silently when Ollama / mq-learn is unavailable — commits must never
    fail or stall because of this.
  * Extraction is always dry-run (learn_extract_pattern, approve=False).
  * Only grounded candidates (non-empty evidence, confidence medium|high) are
    kept; low-confidence / empty-evidence output is dropped.
  * Deduped against both the curated store and the existing inbox by word
    overlap, so the same lesson is not re-queued on every related commit.

Inbox records carry status="pending" and the source commit sha, ready for
review via the learn_inbox MCP tool and promotion via record_learning.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "mq-mcp"
INBOX_FILE = REPO_ROOT / "learn_engine" / "memory" / "inbox.jsonl"
LOG_FILE = REPO_ROOT / "learn_engine" / "memory" / "post-commit.log"
LESSONS_FILE = REPO_ROOT / "learn_engine" / "memory" / "lessons.jsonl"

MAX_DIFF_CHARS = 6000   # cap the diff fed to the model
DEDUP_THRESHOLD = 0.6   # Jaccard word-overlap above which a candidate is a dup

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def _log(message: str) -> None:
    """Append a timestamped line to the post-commit log (best-effort)."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
        )
        return proc.stdout
    except Exception:
        return ""


def commit_findings(sha: str = "HEAD") -> tuple[str, str]:
    """Return (commit_sha, findings_text) for the given commit.

    The findings text is a compact, untrusted description of the change:
    subject + body + name-status + truncated diff. It is consumed by the
    model as data, never as instructions.
    """
    full_sha = _git("rev-parse", sha).strip()
    subject = _git("log", "-1", "--pretty=%s", sha).strip()
    body = _git("log", "-1", "--pretty=%b", sha).strip()
    name_status = _git("show", "--name-status", "--pretty=format:", sha).strip()
    diff = _git("show", "--pretty=format:", "--unified=2", sha)
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n... (diff truncated)"

    parts = [f"Commit: {subject}"]
    if body:
        parts.append(body)
    if name_status:
        parts.append("Files changed:\n" + name_status)
    if diff.strip():
        parts.append("Diff:\n" + diff)
    return full_sha, "\n\n".join(parts)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _candidate_text(record: dict) -> str:
    return " ".join(
        str(record.get(k, "")) for k in ("pattern_name", "summary", "lesson", "task")
    )


def _existing_word_sets() -> list[set[str]]:
    """Word sets for every curated lesson and queued inbox candidate."""
    sets: list[set[str]] = []
    for path in (LESSONS_FILE, INBOX_FILE):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _candidate_text(rec)
            if text.strip():
                sets.append(_words(text))
    return sets


def is_duplicate(record: dict, existing: list[set[str]]) -> bool:
    words = _words(_candidate_text(record))
    if not words:
        return True
    return any(
        prev and len(words & prev) / len(words | prev) > DEDUP_THRESHOLD
        for prev in existing
    )


def append_inbox(record: dict, sha: str) -> None:
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "status": "pending",
        "source": "post-commit",
        "commit": sha[:12],
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "pattern_name": record.get("pattern_name", ""),
        "pattern_type": record.get("pattern_type", ""),
        "confidence": record.get("confidence", ""),
        "summary": record.get("summary", ""),
        "evidence": record.get("evidence", []),
        "recommended_action": record.get("recommended_action", ""),
    }
    with INBOX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(sha: str = "HEAD") -> str:
    """Extract and queue a candidate. Returns a short status string."""
    try:
        import learn_engine as eng  # noqa: PLC0415
    except Exception as exc:
        return f"skip: learn_engine import failed: {exc}"

    status = eng.ollama_learn_status()
    if status.get("status") != "ready":
        return f"skip: ollama {status.get('status')} ({status.get('reason', '-')})"

    full_sha, findings = commit_findings(sha)
    if not findings.strip():
        return "skip: empty commit findings"

    repo_context = eng.load_repo_context_snapshot(REPO_ROOT)
    try:
        record = eng.learn_extract_pattern(
            findings, approve=False, repo_context=repo_context
        )
    except Exception as exc:
        return f"skip: extraction failed: {exc}"

    confidence = str(record.get("confidence", "")).lower()
    evidence = record.get("evidence") or []
    if confidence not in {"medium", "high"} or not evidence:
        return f"skip: low-signal (confidence={confidence or '-'}, evidence={len(evidence)})"

    if is_duplicate(record, _existing_word_sets()):
        return f"skip: duplicate of an existing lesson/candidate ({record.get('pattern_name', '-')})"

    append_inbox(record, full_sha)
    return f"queued: {record.get('pattern_name', '-')} (confidence={confidence})"


def main() -> int:
    result = run()
    _log(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
