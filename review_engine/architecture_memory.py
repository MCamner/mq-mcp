"""
Architecture Memory — mq-mcp review engine, v1.2.0.

Manages structured ADR-style entries that record why the system is designed
as it is — not just what the review engine found. Complements ReviewMemory
(which stores review findings) with durable architectural intent.

Directory layout under architecture_memory/:
  decisions/   — accepted design decisions (ADR-NNN-slug.md)
  rejected/    — explicitly rejected patterns (REJ-NNN-slug.md)
  boundaries/  — system boundary definitions (BND-NNN-slug.md)
  philosophy/  — stable invariants (PHI-NNN-slug.md)

Each file has a YAML-style frontmatter block:
  ---
  id: ADR-001
  title: ...
  date: YYYY-MM-DD
  status: accepted | rejected | stable | superseded
  area: comma-separated keywords for file-path matching
  ---

Usage:
  from review_engine.architecture_memory import ArchitectureMemory
  mem = ArchitectureMemory()
  entries = mem.list_all()
  text = mem.get("ADR-001")
  relevant = mem.relevant_for("mq-mcp/server.py", max_items=3)
  new_id = mem.record(category="decisions", title="...", area="safety",
                      decision="...", rationale="...", consequences="...")
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_ROOT = REPO_ROOT / "architecture_memory"

_CATEGORIES = ("decisions", "rejected", "boundaries", "philosophy")

# Frontmatter field regex
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)

# ID prefix per category
_ID_PREFIX = {
    "decisions": "ADR",
    "rejected": "REJ",
    "boundaries": "BND",
    "philosophy": "PHI",
}


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    return dict(_FIELD_RE.findall(m.group(1)))


class ArchitectureMemory:
    """Read/write interface for the architecture_memory/ ADR store."""

    def __init__(self, root: Path = MEMORY_ROOT) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        for cat in _CATEGORIES:
            (self._root / cat).mkdir(exist_ok=True)

    # ── reading ───────────────────────────────────────────────────────────────

    def list_all(self) -> list[dict[str, str]]:
        """Return metadata dicts for all entries, sorted by id."""
        entries: list[dict[str, str]] = []
        for cat in _CATEGORIES:
            for p in sorted((self._root / cat).glob("*.md")):
                fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
                if fm.get("id"):
                    fm["category"] = cat
                    fm["file"] = str(p.relative_to(self._root))
                    entries.append(fm)
        entries.sort(key=lambda e: e.get("id", ""))
        return entries

    def list_by_category(self, category: str) -> list[dict[str, str]]:
        """Return metadata dicts for all entries in a category."""
        if category not in _CATEGORIES:
            return []
        results = []
        for p in sorted((self._root / category).glob("*.md")):
            fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
            if fm.get("id"):
                fm["category"] = category
                fm["file"] = str(p.relative_to(self._root))
                results.append(fm)
        return results

    def get(self, adr_id: str) -> Optional[str]:
        """Return full text of an entry by id (e.g. 'ADR-001'), or None."""
        for cat in _CATEGORIES:
            for p in (self._root / cat).glob("*.md"):
                fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
                if fm.get("id", "").upper() == adr_id.upper():
                    return p.read_text(encoding="utf-8")
        return None

    def relevant_for(self, file_path: str, max_items: int = 3) -> list[dict[str, str]]:
        """Return ADRs relevant to a file path based on area keyword matching.

        Matches area keywords against the file path (case-insensitive).
        Philosophy entries are included for all files (they are global invariants).
        Returns at most max_items entries, decisions first.
        """
        rel = file_path.replace("\\", "/").lower()
        scored: list[tuple[int, dict]] = []

        for entry in self.list_all():
            area_raw = entry.get("area", "")
            keywords = [k.strip().lower() for k in area_raw.split(",") if k.strip()]
            cat = entry.get("category", "")

            # Philosophy entries match all files
            if cat == "philosophy":
                scored.append((10, entry))
                continue

            # Count matching keywords
            matches = sum(1 for kw in keywords if kw in rel or kw in rel.split("/")[-1])
            if matches > 0:
                # Decisions rank higher than boundaries and rejected
                rank_bonus = {"decisions": 3, "boundaries": 2, "rejected": 1}.get(cat, 0)
                scored.append((matches * 10 + rank_bonus, entry))

        # Sort descending by score, take top max_items
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:max_items]]

    def format_context_block(self, file_path: str, max_items: int = 3) -> str:
        """Return a compact context block of relevant ADRs for review injection."""
        relevant = self.relevant_for(file_path, max_items=max_items)
        if not relevant:
            return ""

        lines = ["## Relevant architecture decisions"]
        for entry in relevant:
            adr_id = entry.get("id", "")
            title = entry.get("title", "")
            lines.append(f"\n**{adr_id}** — {title}")

            # Include the decision body (first paragraph after ## Decision)
            full_text = self.get(adr_id) or ""
            decision_body = _extract_section(full_text, "Decision")
            if decision_body:
                # Cap at 300 chars to keep context tight
                short = decision_body[:300].strip()
                if len(decision_body) > 300:
                    short += "…"
                lines.append(short)

        return "\n".join(lines)

    # ── writing ───────────────────────────────────────────────────────────────

    def record(
        self,
        title: str,
        area: str,
        decision: str,
        rationale: str,
        consequences: str = "",
        category: str = "decisions",
        status: str = "accepted",
    ) -> str:
        """Write a new ADR entry. Returns the assigned id (e.g. 'ADR-007')."""
        if category not in _CATEGORIES:
            raise ValueError(f"category must be one of {_CATEGORIES}")

        prefix = _ID_PREFIX[category]
        existing = list((self._root / category).glob("*.md"))
        next_num = len(existing) + 1
        adr_id = f"{prefix}-{next_num:03d}"

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
        filename = f"{adr_id}-{slug}.md"

        body_parts = [
            f"---",
            f"id: {adr_id}",
            f"title: {title}",
            f"date: {date.today().isoformat()}",
            f"status: {status}",
            f"area: {area}",
            f"---",
            "",
            "## Decision",
            "",
            decision.strip(),
            "",
            "## Rationale",
            "",
            rationale.strip(),
        ]
        if consequences.strip():
            body_parts += ["", "## Consequences", "", consequences.strip()]

        content = "\n".join(body_parts) + "\n"
        (self._root / category / filename).write_text(content, encoding="utf-8")
        return adr_id

    def format_list(self) -> str:
        """Return a human-readable table of all entries."""
        entries = self.list_all()
        if not entries:
            return "No architecture memory entries found."
        lines = [f"{'ID':<10} {'Status':<12} {'Category':<12} Title"]
        lines.append("-" * 72)
        for e in entries:
            lines.append(
                f"{e.get('id',''):<10} {e.get('status',''):<12} "
                f"{e.get('category',''):<12} {e.get('title','')}"
            )
        return "\n".join(lines)


def _extract_section(text: str, heading: str) -> str:
    """Extract the body of a markdown section by heading name."""
    pattern = re.compile(
        rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)", re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        return ""
    return m.group(1).strip()
