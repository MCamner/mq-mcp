"""
Review Memory — mq-mcp review engine, Phase 3.

Local persistent store for review history.
Each review is saved as a JSON entry indexed by file path and timestamp.
Past findings are retrieved and injected as context for future reviews of the same file.

Storage: review_engine/memory/review_history.json

Usage:
  from review_engine.review_memory import ReviewMemory
  mem = ReviewMemory()
  mem.save(path, mode, findings_text, finding_count, severity_counts)
  past = mem.get_last(path)
  context = mem.format_past_context(path)
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "review_engine" / "memory"
HISTORY_FILE = MEMORY_DIR / "review_history.json"

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
        self._data: dict[str, list[dict]] = self._load()

    def _load(self) -> dict[str, list[dict]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save(
        self,
        file_path: str,
        mode: str,
        findings_text: str,
        finding_count: int,
        severity_counts: dict[str, int],
        model: str = "",
        skill: str = "",
    ) -> None:
        """Persist a completed review to history."""
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
        if file_path not in self._data:
            self._data[file_path] = []
        entries = self._data[file_path]
        entries.insert(0, asdict(entry))
        # Cap history per file
        self._data[file_path] = entries[:MAX_ENTRIES_PER_FILE]
        self._save()

    def get_last(self, file_path: str) -> ReviewEntry | None:
        """Return the most recent review entry for a file, or None."""
        entries = self._data.get(file_path, [])
        if not entries:
            return None
        try:
            return ReviewEntry(**entries[0])
        except Exception:
            return None

    def get_history(self, file_path: str) -> list[ReviewEntry]:
        """Return all review entries for a file, newest first."""
        entries = self._data.get(file_path, [])
        result = []
        for e in entries:
            try:
                result.append(ReviewEntry(**e))
            except Exception:
                continue
        return result

    def format_past_context(self, file_path: str) -> str:
        """
        Return a short summary of past findings for a file to inject as review context.

        Returns empty string if no history exists.
        """
        last = self.get_last(file_path)
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
        """Return all file paths that have review history."""
        return sorted(self._data.keys())

    def summary(self) -> str:
        """Return a human-readable summary of the review history."""
        if not self._data:
            return "No review history."

        lines = [f"Review history: {len(self._data)} files", ""]
        for fp in self.all_files():
            entries = self._data[fp]
            if not entries:
                continue
            last = entries[0]
            age_days = (time.time() - last.get("timestamp", 0)) / 86400
            age_str = f"{age_days:.0f}d ago" if age_days >= 1 else "today"
            count = last.get("finding_count", 0)
            mode = last.get("mode", "?")
            lines.append(f"  {fp}")
            lines.append(f"    last: {mode} review, {age_str}, {count} findings  ({len(entries)} total)")
        return "\n".join(lines)


if __name__ == "__main__":
    mem = ReviewMemory()
    print(mem.summary())
