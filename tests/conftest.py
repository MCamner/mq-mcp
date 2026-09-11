"""Keep the tracked review-memory store out of the test suite.

`review_engine/memory/review_history.json` is tracked. Tests reached it through
`ReviewMemory`'s default path and appended real entries, so a full suite run
left the working tree dirty and `git add -A` would have committed generated
review history (#69).

Two things happen here, and the second is the one that lasts:

- every test gets its own store, so no test writes the tracked file;
- the tracked file is hashed before and after the session, so any write path
  that is added later fails the run instead of being spotted by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRACKED_HISTORY = ROOT / "review_engine" / "memory" / "review_history.json"


@pytest.fixture(autouse=True)
def isolated_review_memory(tmp_path, monkeypatch):
    """Point the default review-memory store at this test's own directory."""
    from review_engine import review_memory

    monkeypatch.setattr(
        review_memory, "HISTORY_FILE", tmp_path / "review_history.json"
    )


@pytest.fixture(scope="session", autouse=True)
def tracked_review_history_is_never_written():
    """Fail the session if anything wrote the tracked store.

    Broader than the redirect above on purpose: it holds regardless of which
    code path did the writing.
    """
    before = TRACKED_HISTORY.read_bytes() if TRACKED_HISTORY.exists() else None
    yield
    after = TRACKED_HISTORY.read_bytes() if TRACKED_HISTORY.exists() else None
    assert after == before, (
        f"the test suite modified the tracked {TRACKED_HISTORY.relative_to(ROOT)}. "
        "Give the test its own store instead of writing the repository's."
    )
