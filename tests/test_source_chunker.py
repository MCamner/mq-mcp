"""A file too large to send in one piece must still be reviewed.

`review_file` refused anything over 200 KB. In mq-mcp that is one file —
`mq-mcp/server.py`, 207 KB — but it is 26% of the repo's own Python and the
largest, most tangled part of it. A gate that is permanently silent about its
biggest file reports "no findings" for the place findings are most likely.

Chunks carry the line number each one starts at, so a finding keeps its
position in the whole file rather than in the fragment it was found in.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from review_engine.source_chunker import split_for_review


def _source(function_count: int, body_lines: int = 3) -> str:
    parts = ['"""Module."""', ""]
    for i in range(function_count):
        parts.append(f"def function_{i}():")
        for j in range(body_lines):
            parts.append(f"    value_{j} = {j}  # padding to give the chunk some size")
        parts.append("")
    return "\n".join(parts)


def test_a_small_file_is_one_chunk_starting_at_line_one():
    source = _source(3)
    chunks = split_for_review(source, max_bytes=100_000)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].text == source


def test_a_large_file_is_split_into_several_chunks():
    source = _source(200)
    chunks = split_for_review(source, max_bytes=2_000)
    assert len(chunks) > 1


def test_every_line_survives_exactly_once_and_in_order():
    """Splitting must not drop or duplicate code — that would be silence again."""
    source = _source(120)
    chunks = split_for_review(source, max_bytes=2_000)
    rejoined = "\n".join(chunk.text for chunk in chunks)
    assert rejoined.splitlines() == source.splitlines()


def test_start_line_points_at_the_real_line_in_the_whole_file():
    source = _source(120)
    lines = source.splitlines()
    for chunk in split_for_review(source, max_bytes=2_000):
        first = chunk.text.splitlines()[0]
        assert lines[chunk.start_line - 1] == first, (
            f"chunk claims line {chunk.start_line}, which is "
            f"{lines[chunk.start_line - 1]!r}, not {first!r}"
        )


def test_python_is_split_between_definitions_not_inside_one():
    """A function cut in half reviews as broken code and invites false findings."""
    source = _source(60, body_lines=6)
    for chunk in split_for_review(source, max_bytes=1_500):
        text = chunk.text
        # A chunk may start with blank lines or the module docstring, but once a
        # def appears the chunk must not begin mid-body.
        first_code = next(
            (line for line in text.splitlines() if line.strip()), ""
        )
        assert not first_code.startswith("    "), f"chunk starts mid-body: {first_code!r}"


def test_a_single_oversized_definition_is_still_emitted():
    """Better one too-large chunk than a silently dropped function."""
    body = "\n".join(f"    x_{i} = {i}" for i in range(400))
    source = f"def enormous():\n{body}\n"
    chunks = split_for_review(source, max_bytes=200)
    assert len(chunks) >= 1
    assert "def enormous():" in chunks[0].text
    assert "\n".join(c.text for c in chunks).splitlines() == source.splitlines()


def test_unparseable_python_falls_back_to_line_splitting():
    source = "def (((:\n" + "\n".join(f"line {i}" for i in range(300))
    chunks = split_for_review(source, max_bytes=500, filename="broken.py")
    assert len(chunks) > 1
    assert "\n".join(c.text for c in chunks).splitlines() == source.splitlines()


def test_non_python_is_split_by_lines():
    source = "\n".join(f"# heading {i}\ntext for section {i}" for i in range(300))
    chunks = split_for_review(source, max_bytes=1_000, filename="notes.md")
    assert len(chunks) > 1
    assert "\n".join(c.text for c in chunks).splitlines() == source.splitlines()


def test_empty_content_yields_nothing_to_review():
    assert split_for_review("", max_bytes=1_000) == []
