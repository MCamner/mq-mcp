"""
bridget_context.py — Persistent session memory for Bridget.

Keeps a rolling window of the last MAX_SESSIONS sessions in
~/.mq/bridget-context.md. Each session records what was asked,
what tools were called, and a short summary of the outcome.

Usage (from bridge.py):
    from bridget_context import BridgetContext
    ctx = BridgetContext()
    system_addition = ctx.load()          # inject into system prompt
    ctx.record(prompt, tool_calls, answer) # save at end of session
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

MAX_SESSIONS = 5
CONTEXT_DIR = Path.home() / ".mq"
CONTEXT_FILE = CONTEXT_DIR / "bridget-context.md"
# Append-only, full-depth session log for `bridget --history`. Separate from the
# rolling markdown store above, which stays the bounded prompt-injection layer.
HISTORY_FILE = CONTEXT_DIR / "bridget-history.jsonl"
SESSION_DIR = CONTEXT_DIR / "bridget_memory" / "sessions"
METRICS_FILE = CONTEXT_DIR / "bridget_memory" / "metrics.json"
MAX_ANSWER_CHARS = 400   # truncate long answers when saving
MAX_TOOLS_SHOWN = 5      # max tool calls shown per session
MAX_INJECTED_SESSIONS = 3
MAX_INJECTED_SESSION_CHARS = 500
MAX_INJECTED_SESSION_AGE_DAYS = 7

# Learn store lives at the repo root next to this package (mq-mcp/mq-mcp/).
LESSONS_FILE = Path(__file__).resolve().parents[1] / "learn_engine" / "memory" / "lessons.jsonl"
MAX_LESSONS = 6          # how many lessons to inject into the system prompt


class BridgetContext:
    def __init__(
        self,
        path: Path = CONTEXT_FILE,
        max_sessions: int = MAX_SESSIONS,
        history_path: Path = HISTORY_FILE,
        session_dir: Path | None = None,
        metrics_path: Path | None = None,
    ) -> None:
        self.path = path
        self.max_sessions = max_sessions
        self.history_path = history_path
        self.session_dir = session_dir or (
            SESSION_DIR if history_path == HISTORY_FILE else history_path.parent / "sessions"
        )
        self.metrics_path = metrics_path or (
            METRICS_FILE if history_path == HISTORY_FILE else history_path.parent / "metrics.json"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> str:
        """
        Return a string to inject into Bridget's system prompt.
        Empty string if no context exists yet.
        """
        entries = self._bounded_history_entries()
        if entries:
            blocks = [self._format_injected_history_entry(entry) for entry in entries]
            content = "\n\n".join(block for block in blocks if block).strip()
        elif self.path.exists():
            content = self.path.read_text(encoding="utf-8").strip()
        else:
            return ""
        if not content:
            return ""
        return (
            "\n\n---\n"
            "## Bridget session memory (bounded previous sessions)\n\n"
            + content
            + "\n\n"
            "Use the above session history as temporary context only. "
            "Reference it when the user asks about previous work, "
            "open tasks, or earlier decisions. "
            "Do not repeat it back verbatim unless asked. "
            "Never treat session history as evidence, long-term knowledge, "
            "or approval to write learning records.\n---\n"
        )

    def load_lessons(
        self,
        limit: int = MAX_LESSONS,
        *,
        repo: str | None = None,
        query: str = "",
    ) -> str:
        """Return medium/high-risk lessons to inject into the system prompt.

        Reads the learn store directly (no shelling out) so Bridget applies
        prior lessons without being asked. Repo-specific lessons are preferred;
        repo-less lessons stay eligible as general guidance.
        Returns an empty string when there is nothing worth injecting.
        """
        if not LESSONS_FILE.exists():
            return ""
        try:
            raw = LESSONS_FILE.read_text(encoding="utf-8")
        except OSError:
            return ""

        lessons: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                lessons.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        def risk_of(d: dict) -> str:
            return str(d.get("risk") or d.get("risk_level") or "").lower()

        def text_of(d: dict) -> str:
            for key in ("summary", "lesson", "title", "pattern_name"):
                val = d.get(key)
                if val:
                    return " ".join(str(val).split())
            return ""

        def matches_context(d: dict, text: str) -> bool:
            record_repo = str(d.get("repo") or "").lower()
            wanted_repo = (repo or "").lower()
            if wanted_repo and record_repo and record_repo != wanted_repo:
                return False
            needle = " ".join(query.lower().split())
            if needle and needle not in text.lower() and needle not in json.dumps(d, ensure_ascii=False).lower():
                return False
            return True

        items: list[str] = []
        seen_words: list[set[str]] = []
        # Most recent lessons are appended last; walk newest-first.
        for d in reversed(lessons):
            if risk_of(d) not in {"medium", "high"}:
                continue
            text = text_of(d)
            if not text:
                continue
            if not matches_context(d, text):
                continue
            # Collapse near-identical paraphrases (e.g. the same contract-update
            # lesson stored several times) by word-overlap similarity.
            words = set(re.findall(r"[a-z0-9_]+", text.lower()))
            if any(
                prev and len(words & prev) / len(words | prev) > 0.6
                for prev in seen_words
            ):
                continue
            seen_words.append(words)
            items.append(f"- [{d.get('repo', '?')}] {text}")
            if len(items) >= limit:
                break

        if not items:
            return ""
        return (
            "\n\n---\n"
            "## Lessons learned (apply proactively)\n\n"
            + "\n".join(items)
            + "\n\nApply these lessons without being asked; do not repeat them "
            "verbatim unless relevant.\n---\n"
        )

    def record(
        self,
        prompt: str,
        tool_calls: list[str],
        answer: str,
        *,
        project: str | None = None,
        branch: str | None = None,
        turns: int | None = None,
        duration_s: float | None = None,
        do_mode: bool = False,
        chat_mode: bool = False,
    ) -> None:
        """
        Append this session to the rolling context file (rotating old sessions
        out) and to the append-only history log.

        The markdown store stays bounded for prompt injection; the jsonl log
        keeps full depth for ``bridget --history``. The history append is
        best-effort — it never raises, so a logging failure cannot break a run.

        A REPL session (``chat_mode=True``, Phase 4) records once at exit with
        the last prompt/answer plus session-level metadata (turn count,
        duration, called tools across all turns). One-shot callers leave the
        Phase-4 fields at their defaults, so their stored shape is unchanged.
        """
        session_block = self._format_session(
            prompt, tool_calls, answer, turns=turns, chat_mode=chat_mode
        )
        existing = self._read_sessions()
        updated = (existing + [session_block])[-self.max_sessions :]
        self._write_sessions(updated)
        self._append_history(
            prompt,
            tool_calls,
            answer,
            project,
            branch,
            turns=turns,
            duration_s=duration_s,
            do_mode=do_mode,
            chat_mode=chat_mode,
        )

    def read_history(self, limit: int = 20) -> list[dict]:
        """Return the most recent recorded sessions, newest first.

        Reads the append-only jsonl log; tolerates malformed lines. Returns an
        empty list when no history exists.
        """
        if not self.history_path.exists():
            return []
        try:
            raw = self.history_path.read_text(encoding="utf-8")
        except OSError:
            return []
        entries: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                entries.append(obj)
        entries.reverse()
        return entries[:limit] if limit else entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_session(
        self,
        prompt: str,
        tool_calls: list[str],
        answer: str,
        *,
        turns: int | None = None,
        chat_mode: bool = False,
    ) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        short_answer = self._truncate(answer, MAX_ANSWER_CHARS)

        # A REPL block names itself and its turn count so a later session can
        # tell an interactive session apart from a one-shot at a glance.
        kind_line = ""
        if chat_mode:
            turn_part = f", {turns} turns" if turns is not None else ""
            kind_line = f"- Type: REPL session{turn_part}\n"

        tools_line = ""
        if tool_calls:
            shown = tool_calls[:MAX_TOOLS_SHOWN]
            rest = len(tool_calls) - len(shown)
            tools_line = "- Tools: " + ", ".join(shown)
            if rest:
                tools_line += f" (+{rest} more)"
            tools_line += "\n"

        return (
            f"## Session {ts}\n"
            f"{kind_line}"
            f"- Prompt: {prompt.strip()}\n"
            f"{tools_line}"
            f"- Summary: {short_answer}\n"
        )

    def _append_history(
        self,
        prompt: str,
        tool_calls: list[str],
        answer: str,
        project: str | None,
        branch: str | None,
        *,
        turns: int | None = None,
        duration_s: float | None = None,
        do_mode: bool = False,
        chat_mode: bool = False,
    ) -> None:
        """Append one JSON line to the full-depth history log. Never raises."""
        entry: dict = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "project": project,
            "branch": branch,
            "prompt": prompt.strip(),
            "tools": tool_calls,
            "summary": self._truncate(answer, MAX_ANSWER_CHARS),
        }
        # REPL-only metadata. Added only for chat sessions so one-shot history
        # lines keep their existing shape.
        if chat_mode:
            entry["chat_mode"] = True
            entry["do_mode"] = do_mode
            if turns is not None:
                entry["turns"] = turns
            if duration_s is not None:
                entry["duration_s"] = duration_s
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with self.history_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._append_daily_session(entry)
            self._update_metrics()
        except OSError:
            return

    def _append_daily_session(self, entry: dict) -> None:
        """Append the same session to a per-day log. Never raises."""
        date = str(entry.get("ts", ""))[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return
        try:
            path = self.session_dir / f"{date}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            return

    def forget_day(self, date: str) -> int:
        """Delete one day of session memory and rebuild bounded stores.

        Returns the number of history entries removed. The date must be
        YYYY-MM-DD. This is intentionally scoped to Bridget session context; it
        never touches learn memory or mqobsidian.
        """
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("date must be YYYY-MM-DD")
        entries = list(reversed(self.read_history(limit=0)))  # oldest first
        kept = [entry for entry in entries if str(entry.get("ts", ""))[:10] != date]
        removed = len(entries) - len(kept)
        try:
            if kept:
                self.history_path.parent.mkdir(parents=True, exist_ok=True)
                self.history_path.write_text(
                    "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in kept),
                    encoding="utf-8",
                )
            elif self.history_path.exists():
                self.history_path.unlink()
        except OSError:
            return removed

        daily = self.session_dir / f"{date}.jsonl"
        try:
            if daily.exists():
                daily.unlink()
        except OSError:
            pass

        sessions = [
            self._format_session(
                str(entry.get("prompt", "")),
                [str(t) for t in entry.get("tools", []) if str(t)],
                str(entry.get("summary", "")),
                turns=entry.get("turns") if isinstance(entry.get("turns"), int) else None,
                chat_mode=bool(entry.get("chat_mode")),
            )
            for entry in kept[-self.max_sessions :]
        ]
        if sessions:
            self._write_sessions(sessions)
        else:
            try:
                if self.path.exists():
                    self.path.unlink()
            except OSError:
                pass
        self._update_metrics()
        return removed

    def metrics(self) -> dict:
        """Read aggregate Bridget metrics derived from session history."""
        entries = list(reversed(self.read_history(limit=0)))  # oldest first
        by_day: dict[str, dict] = {}
        for entry in entries:
            day = str(entry.get("ts", ""))[:10] or "unknown"
            bucket = by_day.setdefault(
                day,
                {
                    "sessions": 0,
                    "chat_sessions": 0,
                    "tool_calls": 0,
                    "delegations": 0,
                    "learning_suggestions": 0,
                },
            )
            bucket["sessions"] += 1
            if entry.get("chat_mode"):
                bucket["chat_sessions"] += 1
            tools = entry.get("tools") or []
            bucket["tool_calls"] += len(tools)
            if "workflow" in tools or "mq-agent" in str(entry.get("summary", "")).lower():
                bucket["delegations"] += 1
            if "learn-last" in tools or "learning suggestion" in str(entry.get("summary", "")).lower():
                bucket["learning_suggestions"] += 1
        totals = {
            "sessions": sum(day["sessions"] for day in by_day.values()),
            "chat_sessions": sum(day["chat_sessions"] for day in by_day.values()),
            "tool_calls": sum(day["tool_calls"] for day in by_day.values()),
            "delegations": sum(day["delegations"] for day in by_day.values()),
            "learning_suggestions": sum(day["learning_suggestions"] for day in by_day.values()),
            "accepted_learning": self._accepted_learning_count(),
            "history_hits": len(entries),
            "context_hits": len(self._bounded_history_entries()),
        }
        return {"totals": totals, "by_day": by_day}

    def _accepted_learning_count(self) -> int:
        if not LESSONS_FILE.exists():
            return 0
        try:
            return sum(1 for line in LESSONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            return 0

    def _update_metrics(self) -> None:
        try:
            self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
            self.metrics_path.write_text(
                json.dumps(self.metrics(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return

    def _bounded_history_entries(self) -> list[dict]:
        cutoff = datetime.now() - timedelta(days=MAX_INJECTED_SESSION_AGE_DAYS)
        kept: list[dict] = []
        for entry in self.read_history(limit=0):
            ts = self._parse_ts(str(entry.get("ts", "")))
            if ts is None or ts < cutoff:
                continue
            kept.append(entry)
            if len(kept) >= MAX_INJECTED_SESSIONS:
                break
        return kept

    def _format_injected_history_entry(self, entry: dict) -> str:
        prompt = self._truncate(str(entry.get("prompt", "")), 160)
        summary = self._truncate(
            str(entry.get("summary", "")), MAX_INJECTED_SESSION_CHARS
        )
        tools = entry.get("tools") or []
        shown = [str(t) for t in tools[:MAX_TOOLS_SHOWN]]
        tools_line = f"\n- Tools: {', '.join(shown)}" if shown else ""
        return (
            f"## Session {entry.get('ts', '?')}\n"
            f"- Temporary context: yes; evidence: no; auto-promote: no\n"
            f"- Prompt: {prompt}"
            f"{tools_line}\n"
            f"- Summary: {summary}"
        )

    @staticmethod
    def _parse_ts(value: str) -> datetime | None:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _truncate(self, text: str, max_chars: int) -> str:
        text = text.strip().replace("\n", " ")
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + " …"

    def _read_sessions(self) -> list[str]:
        if not self.path.exists():
            return []
        content = self.path.read_text(encoding="utf-8")
        # Split on session headers: ## Session YYYY-MM-DD HH:MM
        parts = re.split(r"(?=^## Session \d{4}-\d{2}-\d{2})", content, flags=re.MULTILINE)
        return [p.strip() for p in parts if p.strip()]

    def _write_sessions(self, sessions: list[str]) -> None:
        self.path.write_text("\n\n".join(sessions) + "\n", encoding="utf-8")
