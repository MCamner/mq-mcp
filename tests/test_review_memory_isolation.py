"""The suite must not write the repository's own review history (#69).

The store is tracked, so a test that appends to it leaves the working tree
dirty and trains people to ignore an unexpected `git status`.
"""

from __future__ import annotations

from pathlib import Path

from review_engine.review_memory import ReviewMemory

ROOT = Path(__file__).resolve().parents[1]
TRACKED_HISTORY = ROOT / "review_engine" / "memory" / "review_history.json"


def test_the_default_store_is_redirected_during_tests():
    """A no-argument ReviewMemory — how production calls it — must not land here."""
    assert ReviewMemory()._path.resolve() != TRACKED_HISTORY.resolve()


def test_production_still_defaults_to_the_tracked_store():
    """The redirect is a test fixture, not a change to where reviews are kept."""
    from review_engine import review_memory

    assert review_memory.HISTORY_FILE.name == "review_history.json"
    assert (
        Path(review_memory.__file__).resolve().parent / "memory" / "review_history.json"
    ).resolve() == TRACKED_HISTORY.resolve()


def test_writing_through_the_default_store_does_not_touch_the_tracked_file():
    before = TRACKED_HISTORY.read_bytes() if TRACKED_HISTORY.exists() else None

    mem = ReviewMemory()
    mem.save(
        "checks.py",
        mode="comment",
        findings_text="[NOTE] checks.py:1\nNothing of note.",
        finding_count=1,
        severity_counts={"NOTE": 1},
        repo="test-isolation",
    )

    after = TRACKED_HISTORY.read_bytes() if TRACKED_HISTORY.exists() else None
    assert after == before
    assert mem.get_last("checks.py", repo="test-isolation") is not None
