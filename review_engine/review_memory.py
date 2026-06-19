"""
Review Memory — mq-mcp review engine, Phase 3.

Local persistent store for review history, namespaced by repo.
Each review is saved as a JSON entry indexed by repo, file path and timestamp.
Past findings are retrieved and injected as context for future reviews of the
same file in the same repo.

Storage: review_engine/memory/review_history.json
  { "<repo>": { "<file_path>": [entry, ...] } }

Legacy flat stores ({ "<file_path>": [entry, ...] }) are migrated on load to
the default repo (the mq-mcp repo itself), so existing history is preserved.

Usage:
  from review_engine.review_memory import ReviewMemory
  mem = ReviewMemory()
  mem.save(path, mode, findings_text, finding_count, severity_counts, repo="repo-signal")
  past = mem.get_last(path, repo="repo-signal")
  context = mem.format_past_context(path, repo="repo-signal")
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "review_engine" / "memory"
HISTORY_FILE = MEMORY_DIR / "review_history.json"

# Reviews with no explicit repo belong to the mq-mcp repo itself.
DEFAULT_REPO = REPO_ROOT.name

MAX_ENTRIES_PER_FILE = 10
MAX_CONTEXT_FINDINGS = 5


@dataclass
class ReviewEntry:
    file_path: str
    mode: str
    timestamp: float
    timestamp_iso: str
    model: str
    finding_count: int
    severity_counts: dict[str, int]
    findings_text: str
    skill: str = ""

    def age_days(self) -> float:
        return (time.time() - self.timestamp) / 86400


class ReviewMemory:
    def __init__(self, history_file: Path = HISTORY_FILE) -> None:
        self._path = history_file
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, list[dict]]] = self._load()

    def _load(self) -> dict[str, dict[str, list[dict]]]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return self._migrate(raw)

    @staticmethod
    def _migrate(raw: dict) -> dict[str, dict[str, list[dict]]]:
        """Wrap a legacy flat store ({path: [entries]}) under the default repo.

        Already-namespaced stores ({repo: {path: [entries]}}) pass through.
        """
        if not isinstance(raw, dict) or not raw:
            return {} if not raw else raw
        first = next(iter(raw.values()))
        if isinstance(first, list):  # legacy flat → namespace under default repo
            return {DEFAULT_REPO: raw}
        return raw

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _repo(repo: str | None) -> str:
        return repo or DEFAULT_REPO

    def _entries(self, file_path: str, repo: str | None) -> list[dict]:
        return self._data.get(self._repo(repo), {}).get(file_path, [])

    def save(
        self,
        file_path: str,
        mode: str,
        findings_text: str,
        finding_count: int,
        severity_counts: dict[str, int],
        model: str = "",
        skill: str = "",
        repo: str | None = None,
    ) -> None:
        """Persist a completed review to history, namespaced by repo."""
        from datetime import datetime, timezone
        entry = ReviewEntry(
            file_path=file_path,
            mode=mode,
            timestamp=time.time(),
            timestamp_iso=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            model=model,
            finding_count=finding_count,
            severity_counts=severity_counts,
            findings_text=findings_text,
            skill=skill,
        )
        repo_map = self._data.setdefault(self._repo(repo), {})
        entries = repo_map.setdefault(file_path, [])
        entries.insert(0, asdict(entry))
        repo_map[file_path] = entries[:MAX_ENTRIES_PER_FILE]
        self._save()

    def get_last(self, file_path: str, repo: str | None = None) -> ReviewEntry | None:
        """Return the most recent review entry for a file in a repo, or None."""
        entries = self._entries(file_path, repo)
        if not entries:
            return None
        try:
            return ReviewEntry(**entries[0])
        except Exception:
            return None

    def get_history(self, file_path: str, repo: str | None = None) -> list[ReviewEntry]:
        """Return all review entries for a file in a repo, newest first."""
        result = []
        for e in self._entries(file_path, repo):
            try:
                result.append(ReviewEntry(**e))
            except Exception:
                continue
        return result

    def get_last_timestamp(self, file_path: str, repo: str | None = None) -> float:
        """Return the timestamp of the most recent review, or 0.0 if none."""
        entries = self._entries(file_path, repo)
        return entries[0].get("timestamp", 0.0) if entries else 0.0

    def format_past_context(self, file_path: str, repo: str | None = None) -> str:
        """
        Return a short summary of past findings for a file to inject as review context.

        Returns empty string if no history exists.
        """
        last = self.get_last(file_path, repo=repo)
        if not last:
            return ""

        age = last.age_days()
        age_str = f"{age:.0f} days ago" if age >= 1 else "today"

        dist = "  ".join(
            f"{k}={v}"
            for k, v in sorted(last.severity_counts.items())
            if v > 0
        )

        lines = [
            f"Previous review ({last.mode} mode, {age_str}, {last.finding_count} findings [{dist}]):",
            "",
        ]

        # Include the top N findings from the last review as context
        finding_blocks = last.findings_text.strip().split("\n\n")
        for block in finding_blocks[:MAX_CONTEXT_FINDINGS]:
            lines.append(block.strip())
            lines.append("")

        if len(finding_blocks) > MAX_CONTEXT_FINDINGS:
            lines.append(f"... and {len(finding_blocks) - MAX_CONTEXT_FINDINGS} more findings.")

        return "\n".join(lines).strip()

    def all_files(self) -> list[str]:
        """Return all reviewed files as '<repo>/<file_path>', sorted."""
        out = []
        for repo, files in self._data.items():
            out.extend(f"{repo}/{fp}" for fp in files)
        return sorted(out)

    def summary(self) -> str:
        """Return a human-readable summary of the review history."""
        if not self._data:
            return "No review history."

        total_files = sum(len(files) for files in self._data.values())
        lines = [f"Review history: {total_files} files across {len(self._data)} repos", ""]
        for repo in sorted(self._data):
            for fp in sorted(self._data[repo]):
                entries = self._data[repo][fp]
                if not entries:
                    continue
                last = entries[0]
                age_days = (time.time() - last.get("timestamp", 0)) / 86400
                age_str = f"{age_days:.0f}d ago" if age_days >= 1 else "today"
                count = last.get("finding_count", 0)
                mode = last.get("mode", "?")
                lines.append(f"  {repo}/{fp}")
                lines.append(f"    last: {mode} review, {age_str}, {count} findings  ({len(entries)} total)")
        return "\n".join(lines)


if __name__ == "__main__":
    mem = ReviewMemory()
    print(mem.summary())
