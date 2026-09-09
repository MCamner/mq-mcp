"""Split a file that is too large to send in one request.

The review tools refused anything over 200 KB and said so in the output. That
reads like a limit being respected, but its effect is that the largest file in
a repo — the one most likely to have accumulated something worth finding — is
the one nothing ever looks at. In mq-mcp that single refusal covers 26% of the
repo's own Python.

Splitting is done between top-level definitions where the file parses, so a
function is reviewed whole rather than as two halves that each look broken. A
chunk carries the line it starts at, so findings can be reported against the
whole file instead of against the fragment they were found in.

Nothing is dropped. A definition larger than the budget is emitted on its own
and left oversized, because a chunk too big to review is a visible problem and
a missing function is not.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """A reviewable slice of a file, and the 1-based line it starts at."""

    start_line: int
    text: str


def _definition_starts(content: str) -> list[int] | None:
    """1-based lines where a top-level definition begins, or None if unparseable.

    Decorators belong to the definition they precede, so the boundary is the
    first decorator rather than the `def` — splitting between them would leave a
    dangling decorator in one chunk and an undecorated function in the next.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    starts: list[int] = []
    for node in tree.body:
        line = node.lineno
        decorators = getattr(node, "decorator_list", None)
        if decorators:
            line = min(line, min(d.lineno for d in decorators))
        starts.append(line)
    return sorted(set(starts))


def _pack(lines: list[str], starts: list[int], max_bytes: int) -> list[Chunk]:
    """Group consecutive segments into chunks that stay under the budget."""
    segments: list[tuple[int, list[str]]] = []
    edges = [s for s in starts if 1 <= s <= len(lines)]
    if not edges or edges[0] != 1:
        edges = [1] + edges

    for index, start in enumerate(edges):
        end = edges[index + 1] if index + 1 < len(edges) else len(lines) + 1
        segments.append((start, lines[start - 1 : end - 1]))

    chunks: list[Chunk] = []
    current_start: int | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_start, current
        if current_start is not None and current:
            chunks.append(Chunk(current_start, "\n".join(current)))
        current_start, current = None, []

    for start, body in segments:
        if not body:
            continue
        size = sum(len(line) + 1 for line in body)
        pending = sum(len(line) + 1 for line in current)

        if current and pending + size > max_bytes:
            flush()

        if current_start is None:
            current_start = start

        current.extend(body)

        # A single definition over budget cannot be helped by more splitting;
        # emit it alone rather than growing the chunk further.
        if size > max_bytes:
            flush()

    flush()
    return chunks


def _by_lines(lines: list[str], max_bytes: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    start = 1
    current: list[str] = []
    for offset, line in enumerate(lines, 1):
        projected = sum(len(item) + 1 for item in current) + len(line) + 1
        if current and projected > max_bytes:
            chunks.append(Chunk(start, "\n".join(current)))
            start = offset
            current = []
        current.append(line)
    if current:
        chunks.append(Chunk(start, "\n".join(current)))
    return chunks


def split_for_review(
    content: str, max_bytes: int, filename: str = "source.py"
) -> list[Chunk]:
    """Split `content` into chunks no larger than `max_bytes` where possible.

    Returns a single chunk when the file already fits, an empty list when there
    is nothing to review, and otherwise chunks in file order whose texts rejoin
    to the original line for line.
    """
    if not content:
        return []

    lines = content.splitlines()
    if not lines:
        return []

    if len(content.encode("utf-8")) <= max_bytes:
        return [Chunk(1, content)]

    starts = _definition_starts(content) if filename.endswith(".py") else None
    if starts:
        packed = _pack(lines, starts, max_bytes)
        if packed:
            return packed
    return _by_lines(lines, max_bytes)
