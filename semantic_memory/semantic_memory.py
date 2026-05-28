"""
Semantic Memory — mq-mcp v1.4.0.

Durable knowledge store for long-term, reusable context that is separate from:
  - architecture_memory/  (ADRs, boundaries, philosophy — structural decisions)
  - review_engine/memory/ (per-file review history — operational)

This layer stores doc summaries, contracts, conventions and cross-repo facts
that should be available across all review and reasoning operations.

Storage: semantic_memory/store.json
Each item: key, content, tags, created_at, updated_at

Integration: injected into review_file context at priority 0 (highest)
when a keyword match is found for the file being reviewed.
"""

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "semantic_memory"
STORE_FILE = STORE_DIR / "store.json"

MAX_SEARCH_RESULTS = 10
PREVIEW_CHARS = 200


@dataclass
class MemoryItem:
    key: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def preview(self) -> str:
        text = self.content.strip()
        return text[:PREVIEW_CHARS] + "…" if len(text) > PREVIEW_CHARS else text


class SemanticMemory:
    def __init__(self) -> None:
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if STORE_FILE.exists():
            try:
                return json.loads(STORE_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        STORE_FILE.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def store(self, key: str, content: str, tags: Optional[list[str]] = None) -> MemoryItem:
        """Store or update a knowledge item. Returns the saved item."""
        tags = tags or []
        now = time.time()
        existing = self._data.get(key)
        item = MemoryItem(
            key=key,
            content=content,
            tags=tags,
            created_at=existing["created_at"] if existing else now,
            updated_at=now,
        )
        self._data[key] = asdict(item)
        self._save()
        return item

    def get(self, key: str) -> Optional[MemoryItem]:
        """Return a single item by exact key, or None."""
        raw = self._data.get(key)
        if raw is None:
            return None
        return MemoryItem(**raw)

    def list_all(self) -> list[MemoryItem]:
        """Return all items sorted by updated_at descending."""
        items = [MemoryItem(**v) for v in self._data.values()]
        return sorted(items, key=lambda x: x.updated_at, reverse=True)

    def search(self, query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[MemoryItem]:
        """
        Keyword search across keys, tags, and content.
        Returns items ranked by match count, capped at max_results.
        """
        terms = [t.lower() for t in re.split(r"\s+", query.strip()) if t]
        if not terms:
            return self.list_all()[:max_results]

        scored: list[tuple[int, MemoryItem]] = []
        for raw in self._data.values():
            item = MemoryItem(**raw)
            haystack = (
                item.key.lower()
                + " "
                + " ".join(item.tags).lower()
                + " "
                + item.content.lower()
            )
            score = sum(haystack.count(t) for t in terms)
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:max_results]]

    def search_for_file(self, file_path: str, max_results: int = 3) -> list[MemoryItem]:
        """
        Find items relevant to a file path.
        Matches on path components and file extension as implicit tags.
        Returns at most max_results items.
        """
        path = Path(file_path)
        terms = [path.stem.lower(), path.suffix.lstrip(".").lower()]
        terms += [p.lower() for p in path.parts if p not in (".", "..")]
        terms = [t for t in terms if len(t) > 2]
        if not terms:
            return []
        query = " ".join(terms)
        return self.search(query, max_results=max_results)

    def format_context_block(self, file_path: str, max_results: int = 3) -> str:
        """Return a formatted context string for injection into review prompts."""
        items = self.search_for_file(file_path, max_results=max_results)
        if not items:
            return ""
        lines = ["## Semantic memory context\n"]
        for item in items:
            tag_str = f"  [{', '.join(item.tags)}]" if item.tags else ""
            lines.append(f"### {item.key}{tag_str}\n{item.preview()}\n")
        return "\n".join(lines)

    def delete(self, key: str) -> bool:
        """Remove an item by key. Returns True if it existed."""
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def item_count(self) -> int:
        return len(self._data)
