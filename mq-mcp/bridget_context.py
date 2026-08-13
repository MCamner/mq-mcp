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
from datetime import datetime
from pathlib import Path

MAX_SESSIONS = 5
CONTEXT_DIR = Path.home() / ".mq"
CONTEXT_FILE = CONTEXT_DIR / "bridget-context.md"
# Append-only, full-depth session log for `bridget --history`. Separate from the
# rolling markdown store above, which stays the bounded prompt-injection layer.
HISTORY_FILE = CONTEXT_DIR / "bridget-history.jsonl"
MAX_ANSWER_CHARS = 400   # truncate long answers when saving
MAX_TOOLS_SHOWN = 5      # max tool calls shown per session

# Learn store lives at the repo root next to this package (mq-mcp/mq-mcp/).
LESSONS_FILE = Path(__file__).resolve().parents[1] / "learn_engine" / "memory" / "lessons.jsonl"
MAX_LESSONS = 6          # how many lessons to inject into the system prompt
MAX_LESSON_CONTEXT_CHARS = 1600
_LESSON_STOP_WORDS = {
    "after", "before", "change", "current", "from", "into", "keep", "task",
    "that", "the", "this", "update", "with",
}


class BridgetContext:
    def __init__(
        self,
        path: Path = CONTEXT_FILE,
        max_sessions: int = MAX_SESSIONS,
        history_path: Path = HISTORY_FILE,
    ) -> None:
        self.path = path
        self.max_sessions = max_sessions
        self.history_path = history_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> str:
        """
        Return a string to inject into Bridget's system prompt.
        Empty string if no context exists yet.
        """
        if not self.path.exists():
            return ""
        content = self.path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        return (
            "\n\n---\n"
            "## Bridget session memory (previous sessions)\n\n"
            + content
            + "\n\n"
            "Use the above session history as context. "
            "Reference it when the user asks about previous work, "
            "open tasks, or earlier decisions. "
            "Do not repeat it back verbatim unless asked.\n---\n"
        )

    def load_lessons(
        self,
        limit: int = MAX_LESSONS,
        *,
        repo: str = "",
        file_path: str = "",
        task: str = "",
        risk_levels: tuple[str, ...] = ("medium", "high"),
        max_chars: int = MAX_LESSON_CONTEXT_CHARS,
    ) -> str:
        """Return bounded lessons relevant to the current repository and task.

        Reads the learn store directly (no shelling out) so Bridget applies
        prior lessons without being asked. Repository and risk are eligibility
        filters; file/task terms rank and filter eligible records. With no
        context arguments this retains the legacy medium/high cross-repo view.
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

        def terms_of(value: object) -> set[str]:
            words = re.findall(r"[a-z0-9_]+", str(value).lower())
            return {
                word[:-1] if len(word) > 4 and word.endswith("s") else word
                for word in words
                if len(word) > 2 and word not in _LESSON_STOP_WORDS
            }

        query_terms = terms_of(task)
        selected_file = file_path.strip().lower()
        allowed_risks = {risk.lower() for risk in risk_levels}
        ranked: list[tuple[int, int, dict, str]] = []
        for recency, d in enumerate(reversed(lessons)):
            if risk_of(d) not in allowed_risks:
                continue
            lesson_repo = str(d.get("repo") or "").strip().lower()
            if repo and lesson_repo not in {"", "general", repo.strip().lower()}:
                continue
            text = text_of(d)
            if not text:
                continue
            files = [str(item).lower() for item in d.get("files_touched", []) or []]
            haystack = " ".join(
                [
                    text,
                    str(d.get("task") or ""),
                    " ".join(str(tag) for tag in d.get("tags", []) or []),
                    " ".join(files),
                ]
            )
            score = len(query_terms & terms_of(haystack))
            if selected_file and any(
                selected_file == candidate
                or Path(selected_file).name == Path(candidate).name
                for candidate in files
            ):
                score += 10
            if (query_terms or selected_file) and score == 0:
                continue
            ranked.append((score, -recency, d, text))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

        items: list[str] = []
        seen_words: list[set[str]] = []
        for _score, _recency, d, text in ranked:
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
        header = (
            "\n\n---\n"
            "## Lessons learned (apply proactively)\n\n"
        )
        footer = (
            "\n\nApply these lessons without being asked; do not repeat them "
            "verbatim unless relevant.\n---\n"
        )
        available = max_chars - len(header) - len(footer)
        if available <= 4:
            return ""
        rendered: list[str] = []
        used = 0
        for item in items:
            separator = 1 if rendered else 0
            remaining = available - used - separator
            if remaining <= 1:
                break
            bounded = item if len(item) <= remaining else item[: remaining - 1].rstrip() + "…"
            rendered.append(bounded)
            used += separator + len(bounded)
            if len(item) > remaining:
                break
        return header + "\n".join(rendered) + footer

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
        except OSError:
            return

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
