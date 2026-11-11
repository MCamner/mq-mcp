#!/usr/bin/env python3
"""post_commit_learn.py — auto-extract a learn candidate from the last commit.

Run by the git post-commit hook (in the background). It feeds the just-made
commit's diff to the local mq-learn Ollama model and writes any grounded,
medium/high-confidence candidate to a *pending inbox* — never to the curated
learn store. Nothing lands in lessons.jsonl without explicit human/agent
promotion, so an auto hook cannot poison the store with hallucinated lessons.

Design choices (deliberate):
  * Never fail or stall a commit. When Ollama / mq-learn or the repo context is
    unavailable the commit is not analysed now, but its SHA is remembered in
    pending-commits.txt and analysed by a later run, so an outage delays
    extraction instead of silently losing it.
  * One extraction is a sample, not a verdict: the local model does not return
    the same answer for an identical prompt, so a low-signal result is retried
    a bounded number of times before the commit is given up on.
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

PENDING_FILE = REPO_ROOT / "learn_engine" / "memory" / "pending-commits.txt"

MAX_DIFF_CHARS = 6000   # cap the diff fed to the model
DEDUP_THRESHOLD = 0.6   # Jaccard word-overlap above which a candidate is a dup
MAX_ATTEMPTS = 3        # extractions per commit before a low-signal result stands
MAX_PENDING = 50        # remembered commits; older ones fall off the front
MAX_DRAIN = 5           # remembered commits analysed per run

# Results that say "this commit was not analysed because of the environment",
# as opposed to "it was analysed and yielded nothing". Only these are retried.
_RETRY_LATER_PREFIXES = (
    "skip: ollama ",
    "skip: learn_engine import failed",
    "skip: no verified repo context",
    "skip: extraction failed: Ollama learn provider unavailable",
)

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


LEARN_MEMORY_PREFIX = "learn_engine/memory/"

#: Returned by commit_findings in place of findings text when a commit changes
#: nothing outside the learn store. Its diff is stored lessons plus their
#: neighbours as context lines, so the model "discovers" a lesson that is
#: already curated (seen 2026-11-11: a lessons-only commit yielded a pattern
#: about another repo, caught only by the duplicate check).
MEMORY_ONLY = "\x00learn-memory-only"

#: Returned by commit_findings when a commit changes no files at all: an
#: `--allow-empty` commit, or a merge commit, whose `git show` lists nothing.
#: There is no diff to learn from, and with the low-signal retry such a commit
#: cost three model calls for a certain "nothing" (measured 2026-11-11).
NO_CHANGES = "\x00no-changed-files"

_SHA_RE = re.compile(r"[0-9a-fA-F]{7,40}")


def _paths_from_name_status(name_status: str) -> list[str]:
    """Changed paths from `git show --name-status` output (renames: both sides)."""
    paths: list[str] = []
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        paths.extend(part.strip() for part in parts[1:] if part.strip())
    return paths


def _only_learn_memory(paths: list[str]) -> bool:
    """True when a commit changes at least one file and all are learn memory."""
    return bool(paths) and all(path.startswith(LEARN_MEMORY_PREFIX) for path in paths)


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
    paths = _paths_from_name_status(name_status)
    if not paths:
        return full_sha, NO_CHANGES
    if _only_learn_memory(paths):
        return full_sha, MEMORY_ONLY
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


def _record_provider_trace(trace: dict, response: object) -> None:
    """Note what the model itself answered, before grounding and validation.

    "low-signal" has two very different causes: the model found nothing, or the
    model found evidence that grounding then dropped. The same commit gave both
    outcomes on 2026-11-11, and the log could not tell them apart.
    """
    try:
        body = response.json() if hasattr(response, "json") else response
        generated = body.get("response") if isinstance(body, dict) else None
        if isinstance(generated, str):
            generated = json.loads(generated)
        if isinstance(generated, dict):
            evidence = generated.get("evidence")
            trace["confidence"] = str(generated.get("confidence") or "-")
            trace["evidence"] = len(evidence) if isinstance(evidence, list) else 0
    except Exception:
        pass


def _tracing_post(trace: dict):
    """requests.post that also records the raw provider answer in ``trace``."""

    def post(*args, **kwargs):
        import requests  # noqa: PLC0415

        response = requests.post(*args, **kwargs)
        _record_provider_trace(trace, response)
        return response

    return post


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
    if findings == NO_CHANGES:
        return "skip: commit changes no files (empty or merge commit)"
    if findings == MEMORY_ONLY:
        return (
            f"skip: commit only touches {LEARN_MEMORY_PREFIX} "
            "(stored lessons are not new evidence)"
        )
    if not findings.strip():
        return "skip: empty commit findings"

    repo_context = eng.load_repo_context_snapshot(REPO_ROOT)
    if not repo_context.strip():
        # learn_extract_pattern would refuse without calling the model and the
        # refusal would be logged as "low-signal", which reads like a model
        # result. Name the real cause instead.
        return (
            "skip: no verified repo context (.repo-signal/exports/symbol_index.json "
            "missing, older than 24h, or for another checkout; "
            "run `repo-signal export . --symbol-index`)"
        )
    # The same commit and the same prompt gave both a high-confidence candidate
    # and a low-signal answer (2026-11-11, fixed seed, 2 of 5 runs low), so a
    # single low answer does not show the commit holds nothing. Ask again, a
    # bounded number of times, and report the last answer if none is usable.
    low_signal = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        trace: dict = {}
        try:
            record = eng.learn_extract_pattern(
                findings,
                approve=False,
                repo_context=repo_context,
                require_repo_context=True,
                http_post=_tracing_post(trace),
            )
        except Exception as exc:
            return f"skip: extraction failed: {exc}"

        confidence = str(record.get("confidence", "")).lower()
        evidence = record.get("evidence") or []
        if confidence in {"medium", "high"} and evidence:
            break
        said = ""
        if trace:
            said = (
                f"; model said confidence={trace['confidence']}, "
                f"evidence={trace['evidence']}"
            )
        low_signal = (
            f"skip: low-signal after {attempt} attempt(s) "
            f"(confidence={confidence or '-'}, evidence={len(evidence)}{said})"
        )
    else:
        return low_signal

    if is_duplicate(record, _existing_word_sets()):
        return f"skip: duplicate of an existing lesson/candidate ({record.get('pattern_name', '-')})"

    append_inbox(record, full_sha)
    tries = f", attempt {attempt}/{MAX_ATTEMPTS}" if attempt > 1 else ""
    return f"queued: {record.get('pattern_name', '-')} (confidence={confidence}{tries})"


def _retry_later(result: str) -> bool:
    """True when a run did not analyse the commit because of the environment."""
    return result.startswith(_RETRY_LATER_PREFIXES)


def _resolve(sha: str) -> str:
    """Full SHA of a commit, or "" when it does not name one in this repo."""
    if sha != "HEAD" and not _SHA_RE.fullmatch(sha):
        return ""
    full = _git("rev-parse", "--verify", "--quiet", sha + "^{commit}").strip()
    return full if _SHA_RE.fullmatch(full) else ""


def _read_pending() -> list[str]:
    """Remembered commit SHAs, oldest first; malformed lines are ignored."""
    try:
        lines = PENDING_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    pending: list[str] = []
    for line in lines:
        sha = line.strip()
        if _SHA_RE.fullmatch(sha) and sha not in pending:
            pending.append(sha)
    return pending


def _write_pending(shas: list[str]) -> None:
    """Replace the pending list (best-effort; never raises into the hook)."""
    try:
        if not shas:
            PENDING_FILE.unlink(missing_ok=True)
            return
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PENDING_FILE.with_suffix(PENDING_FILE.suffix + ".tmp")
        tmp.write_text("\n".join(shas[-MAX_PENDING:]) + "\n", encoding="utf-8")
        tmp.replace(PENDING_FILE)
    except OSError:
        pass


def remember_pending(sha: str) -> None:
    """Keep a commit for a later run. Local, gitignored, bounded."""
    if not _SHA_RE.fullmatch(sha):
        return
    pending = _read_pending()
    if sha not in pending:
        _write_pending([*pending, sha])


def forget_pending(sha: str) -> None:
    pending = _read_pending()
    if sha in pending:
        _write_pending([item for item in pending if item != sha])


def drain_pending(skip: str = "") -> None:
    """Analyse a few remembered commits now that the environment works.

    Stops at the first one that still cannot be analysed, so an outage that
    returns mid-drain keeps the rest. A commit that no longer exists (rebased
    away, garbage-collected) is dropped without asking the model about it.
    """
    for sha in [item for item in _read_pending() if item != skip][:MAX_DRAIN]:
        if not _resolve(sha):
            _log(f"backlog {sha[:12]}: dropped, commit no longer exists")
            forget_pending(sha)
            continue
        result = run(sha)
        _log(f"backlog {sha[:12]}: {result}")
        if _retry_later(result):
            return
        forget_pending(sha)


def main() -> int:
    # The hook passes the SHA it captured at commit time. Reading HEAD here
    # instead analyses whatever is checked out when this background job gets
    # to it: two quick commits were both analysed as the second one.
    sha = "HEAD"
    if len(sys.argv) > 1 and _SHA_RE.fullmatch(sys.argv[1]):
        sha = sys.argv[1]
    result = run(sha)
    _log(result)

    full = _resolve(sha)
    if _retry_later(result):
        if full:
            remember_pending(full)
            _log(f"pending {full[:12]}: kept for a later run")
    else:
        if full:
            forget_pending(full)
        drain_pending(skip=full)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
