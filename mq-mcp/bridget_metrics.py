"""Content-free local usage counters for Bridget.

The store deliberately accepts only a fixed metric vocabulary and persists
only a calendar date plus an integer increment. Prompts, answers, repositories,
paths, tool names, arguments, and session identifiers never enter this file.
Metrics are best-effort and must never make a Bridget command fail.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from bridget_context import CONTEXT_DIR


METRICS_FILE = CONTEXT_DIR / "bridget-metrics.jsonl"
SCHEMA = "bridget-metric.v1"
METRIC_NAMES = (
    "commands",
    "sessions",
    "delegations",
    "learning_suggestions",
    "accepted_learning",
    "history_hits",
    "context_hits",
)
DEFAULT_DAYS = 7
DEFAULT_VALIDATION_DAYS = 30
MAX_DAYS = 365


def _as_date(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value


class BridgetMetrics:
    """Append and aggregate a fixed set of anonymous daily counters."""

    def __init__(self, path: Path = METRICS_FILE) -> None:
        self.path = path

    def record(
        self,
        metric: str,
        *,
        count: int = 1,
        now: date | datetime | None = None,
    ) -> bool:
        """Append one validated counter increment; return False on any failure."""
        if os.getenv("BRIDGET_METRICS_DISABLED", "").lower() in {"1", "true", "yes"}:
            return False
        if metric not in METRIC_NAMES or isinstance(count, bool) or count <= 0:
            return False
        row = {
            "schema": SCHEMA,
            "date": _as_date(now).isoformat(),
            "metric": metric,
            "count": count,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            return True
        except OSError:
            return False

    def daily(
        self,
        *,
        days: int = DEFAULT_DAYS,
        now: date | datetime | None = None,
    ) -> list[dict[str, int | str]]:
        """Return chronological daily totals, including zero-count days."""
        if not 1 <= days <= MAX_DAYS:
            raise ValueError(f"days must be between 1 and {MAX_DAYS}")
        today = _as_date(now)
        first = today - timedelta(days=days - 1)
        rows: dict[str, dict[str, int | str]] = {}
        for offset in range(days):
            day = (first + timedelta(days=offset)).isoformat()
            rows[day] = {"date": day, **{name: 0 for name in METRIC_NAMES}}

        if not self.path.exists():
            return list(rows.values())
        try:
            handle = self.path.open("r", encoding="utf-8")
        except OSError:
            return list(rows.values())
        with handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict) or item.get("schema") != SCHEMA:
                    continue
                day = item.get("date")
                metric = item.get("metric")
                count = item.get("count")
                if (
                    day not in rows
                    or metric not in METRIC_NAMES
                    or isinstance(count, bool)
                    or not isinstance(count, int)
                    or count <= 0
                ):
                    continue
                rows[day][metric] = int(rows[day][metric]) + count
        return list(rows.values())

    def dashboard(
        self,
        *,
        days: int = DEFAULT_DAYS,
        now: date | datetime | None = None,
    ) -> str:
        """Render a compact daily outcome dashboard."""
        rows = self.daily(days=days, now=now)
        day_label = "day" if days == 1 else "days"
        headers = (
            "date",
            "helped",
            "delegated",
            "suggested",
            "accepted",
            "history",
            "context",
            "sessions",
        )
        keys = (
            "commands",
            "delegations",
            "learning_suggestions",
            "accepted_learning",
            "history_hits",
            "context_hits",
            "sessions",
        )
        lines = [
            f"Bridget metrics — last {days} {day_label}",
            "  ".join(f"{header:>10}" for header in headers),
        ]
        totals = {key: 0 for key in keys}
        for row in rows:
            values = [int(row[key]) for key in keys]
            for key, value in zip(keys, values, strict=True):
                totals[key] += value
            lines.append(
                f"{str(row['date']):>10}  "
                + "  ".join(f"{value:>10}" for value in values)
            )
        lines.append(
            f"{'Total':>10}  "
            + "  ".join(f"{totals[key]:>10}" for key in keys)
        )
        lines.append("Local aggregate counters only; no prompt or answer content.")
        return "\n".join(lines)

    def validation_report(
        self,
        *,
        days: int = DEFAULT_VALIDATION_DAYS,
        now: date | datetime | None = None,
    ) -> str:
        """Render transparent Phase 7 signals without inferring usefulness."""
        rows = self.daily(days=days, now=now)
        totals = {name: sum(int(row[name]) for row in rows) for name in METRIC_NAMES}
        active_days = sum(
            1 for row in rows if any(int(row[name]) > 0 for name in METRIC_NAMES)
        )
        commands = totals["commands"]
        suggestions = totals["learning_suggestions"]
        status = (
            "insufficient (no recorded usage)"
            if active_days == 0
            else "observation in progress"
        )

        def ratio(value: int, total: int) -> str:
            percentage = value / total * 100 if total else 0.0
            return f"{percentage:.1f}%"

        return "\n".join(
            (
                f"Bridget Phase 7 validation — last {days} days",
                f"Evidence status: {status}",
                f"Active days: {active_days}/{days}",
                f"Commands / sessions: {commands}/{totals['sessions']}",
                "Delegation rate: "
                f"{ratio(totals['delegations'], commands)} "
                f"({totals['delegations']}/{commands} commands)",
                "Learning acceptance: "
                f"{ratio(totals['accepted_learning'], suggestions)} "
                f"({totals['accepted_learning']}/{suggestions} suggestions)",
                "Context reuse: "
                f"{totals['history_hits'] + totals['context_hits']} hits "
                f"({totals['history_hits']} history, "
                f"{totals['context_hits']} project/repo)",
                "Usefulness cannot be established from aggregate counters alone.",
                "Need for more memory: not established.",
                "Complete the qualitative review in docs/BRIDGET_VALIDATION.md.",
            )
        )


METRICS = BridgetMetrics()


def maybe_handle_metrics_command(
    argv: list[str],
    *,
    metrics: BridgetMetrics = METRICS,
) -> bool:
    """Handle ``bridget --metrics [N]`` without starting OpenAI or MCP."""
    if "--metrics" not in argv:
        return False
    if not 1 <= len(argv) <= 2 or argv[0] != "--metrics":
        print(f"ERROR: usage: bridget --metrics [1-{MAX_DAYS}]")
        return True
    days = DEFAULT_DAYS
    if len(argv) == 2:
        try:
            days = int(argv[1])
        except ValueError:
            days = 0
    if not 1 <= days <= MAX_DAYS:
        print(f"ERROR: usage: bridget --metrics [1-{MAX_DAYS}]")
        return True
    print(metrics.dashboard(days=days))
    return True


def maybe_handle_validation_command(
    argv: list[str],
    *,
    metrics: BridgetMetrics = METRICS,
) -> bool:
    """Handle ``bridget --validation [N]`` without starting OpenAI or MCP."""
    if "--validation" not in argv:
        return False
    if not 1 <= len(argv) <= 2 or argv[0] != "--validation":
        print(f"ERROR: usage: bridget --validation [1-{MAX_DAYS}]")
        return True
    days = DEFAULT_VALIDATION_DAYS
    if len(argv) == 2:
        try:
            days = int(argv[1])
        except ValueError:
            days = 0
    if not 1 <= days <= MAX_DAYS:
        print(f"ERROR: usage: bridget --validation [1-{MAX_DAYS}]")
        return True
    print(metrics.validation_report(days=days))
    return True
