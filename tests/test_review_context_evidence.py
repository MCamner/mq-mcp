"""The loader that decides whether review may trust a context artifact.

ADR-008: refusal is for artifacts that misrepresent their identity, because
that is the failure that cannot be reported honestly. Age and partial coverage
degrade instead, with the limit shown rather than hidden.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from review_engine.context_evidence import (  # noqa: E402
    INVALID,
    MISSING,
    STALE,
    VERIFIED,
    load_review_context,
)

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def _artifact(**overrides) -> dict:
    artifact = {
        "schema": "architecture_map.v1",
        "repo_name": "mq-mcp",
        "generated_at": (NOW - timedelta(hours=2)).isoformat(),
        "file_count": 2,
        "files": {
            "review_engine/router.py": {
                "role": "review engine — context building and routing",
                "public_symbols": ["route_file"],
                "last_review_timestamp": None,
                "hub_score": 3,
            },
            "docs/guide.md": {
                "role": "documentation",
                "public_symbols": [],
                "last_review_timestamp": None,
                "hub_score": 0,
            },
        },
    }
    artifact.update(overrides)
    return artifact


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mq-mcp"
    (repo / "review_engine").mkdir(parents=True, exist_ok=True)
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "review_engine" / "router.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    return repo


def _write(tmp_path: Path, payload) -> Path:
    path = tmp_path / "architecture_map.json"
    path.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )
    return path


def _load(tmp_path: Path, payload=None, *, repo: Path | None = None, now: datetime = NOW, **kw):
    repo = repo or _repo(tmp_path)
    path = _write(tmp_path, _artifact() if payload is None else payload)
    return load_review_context(path, repo_root=repo, expected_repo="mq-mcp", now=now, **kw)


# ── the accepting case ───────────────────────────────────────────────────────

def test_a_current_artifact_verifies(tmp_path):
    result = _load(tmp_path)

    assert result.status == VERIFIED
    assert result.usable is True
    assert result.reasons == []
    assert result.repo_name == "mq-mcp"
    assert result.role_for("review_engine/router.py").startswith("review engine")
    assert result.entry_count == 2


def test_an_unmapped_file_gets_no_role_rather_than_a_guess(tmp_path):
    result = _load(tmp_path)

    assert result.role_for("mq-mcp/brain_ingress.py") == ""


# ── refusals: the artifact is not what it claims to be ───────────────────────

@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (_artifact(schema="architecture_map.v2"), "schema-mismatch"),
        (_artifact(schema=None), "schema-mismatch"),
        ({"repo_name": "mq-mcp", "files": {}}, "schema-mismatch"),
        (_artifact(repo_name="mq-agent"), "repo-mismatch"),
        (_artifact(repo_name=""), "repo-mismatch"),
        ("{ not json", "unparseable"),
        ("[]", "not-an-object"),
        (_artifact(files=[]), "files-malformed"),
        (_artifact(files={"a.py": "just a string"}), "files-malformed"),
        (_artifact(generated_at="not a date"), "generated-at-unparseable"),
        (_artifact(generated_at=None), "generated-at-unparseable"),
    ],
    ids=[
        "wrong-schema", "null-schema", "no-schema",
        "wrong-repo", "empty-repo",
        "malformed-json", "not-an-object",
        "files-not-a-mapping", "entry-not-a-mapping",
        "unparseable-date", "null-date",
    ],
)
def test_identity_failures_are_refused(tmp_path, payload, reason):
    result = _load(tmp_path, payload)

    assert result.status == INVALID
    assert result.usable is False
    assert reason in result.reasons
    assert result.role_for("review_engine/router.py") == ""


def test_a_path_escaping_the_repo_is_refused(tmp_path):
    payload = _artifact(files={"../elsewhere/secrets.py": {"role": "leak"}})

    result = _load(tmp_path, payload)

    assert result.status == INVALID
    assert "path-escapes-repo" in result.reasons


def test_an_absolute_path_is_refused(tmp_path):
    payload = _artifact(files={"/etc/passwd": {"role": "leak"}})

    result = _load(tmp_path, payload)

    assert result.status == INVALID
    assert "path-escapes-repo" in result.reasons


def test_a_future_artifact_is_refused(tmp_path):
    """Evidence from the future contradicts itself, so it is not merely old."""
    payload = _artifact(generated_at=(NOW + timedelta(hours=2)).isoformat())

    result = _load(tmp_path, payload)

    assert result.status == INVALID
    assert "generated-at-in-the-future" in result.reasons


def test_small_clock_skew_is_tolerated(tmp_path):
    payload = _artifact(generated_at=(NOW + timedelta(seconds=30)).isoformat())

    assert _load(tmp_path, payload).status == VERIFIED


# ── missing ──────────────────────────────────────────────────────────────────

def test_a_missing_artifact_says_so(tmp_path):
    result = load_review_context(
        tmp_path / "nope.json", repo_root=_repo(tmp_path), expected_repo="mq-mcp", now=NOW
    )

    assert result.status == MISSING
    assert result.usable is False
    assert "artifact-missing" in result.reasons
    assert result.role_for("review_engine/router.py") == ""


# ── degradation: true, but limited ───────────────────────────────────────────

def test_an_old_artifact_is_used_and_its_age_reported(tmp_path):
    payload = _artifact(generated_at=(NOW - timedelta(days=108)).isoformat())

    result = _load(tmp_path, payload)

    assert result.status == STALE
    assert result.usable is True
    assert "stale" in result.reasons
    assert result.age_hours == pytest.approx(108 * 24, abs=1)
    assert result.role_for("review_engine/router.py").startswith("review engine")


def test_an_entry_whose_file_is_gone_is_dropped_not_fatal(tmp_path):
    repo = _repo(tmp_path)
    payload = _artifact()
    payload["files"]["deleted/ghost.py"] = {"role": "documentation"}

    result = _load(tmp_path, payload, repo=repo)

    assert result.usable is True
    assert result.role_for("deleted/ghost.py") == ""
    assert result.missing_files == ["deleted/ghost.py"]
    assert "entries-without-files" in result.reasons


def test_coverage_is_reported_against_the_repo(tmp_path):
    repo = _repo(tmp_path)
    (repo / "mq-mcp").mkdir()
    (repo / "mq-mcp" / "brain_ingress.py").write_text("x = 1\n", encoding="utf-8")

    result = _load(tmp_path, repo=repo)

    assert result.usable is True
    assert result.entry_count == 2
    assert result.scanned_count == 3
    assert "partial-coverage" in result.reasons


def test_full_coverage_reports_no_gap(tmp_path):
    result = _load(tmp_path)

    assert result.scanned_count == 2
    assert "partial-coverage" not in result.reasons


# ── provenance the operator can read ─────────────────────────────────────────

def test_verified_provenance_names_source_repo_and_time(tmp_path):
    lines = _load(tmp_path).provenance_lines()

    assert lines[0] == "Context"
    text = "\n".join(lines)
    assert "architecture_map.v1" in text
    assert "mq-mcp" in text
    assert "verified" in text


def test_refused_provenance_says_why_and_names_no_source(tmp_path):
    lines = _load(tmp_path, _artifact(repo_name="mq-agent")).provenance_lines()
    text = "\n".join(lines)

    assert "unavailable" in text
    assert "repo-mismatch" in text


def test_degraded_provenance_shows_the_limit(tmp_path):
    payload = _artifact(generated_at=(NOW - timedelta(days=108)).isoformat())

    text = "\n".join(_load(tmp_path, payload).provenance_lines())

    assert "stale" in text
    assert "2592h" in text or "108d" in text


def test_provenance_never_leaks_an_absolute_path(tmp_path):
    for result in (
        _load(tmp_path),
        _load(tmp_path, "{ not json"),
        load_review_context(
            tmp_path / "nope.json", repo_root=_repo(tmp_path),
            expected_repo="mq-mcp", now=NOW,
        ),
    ):
        text = "\n".join(result.provenance_lines())
        assert str(tmp_path) not in text
        assert "/Users/" not in text


# ── the loader is pure ───────────────────────────────────────────────────────

def test_loading_writes_nothing(tmp_path):
    repo = _repo(tmp_path)
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    _load(tmp_path, repo=repo)
    _write(tmp_path, _artifact())

    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    assert after == sorted(set(before) | {Path("architecture_map.json")})


def test_a_refused_result_hands_out_nothing_even_if_it_carries_entries(tmp_path):
    """"Refused contributes nothing" must hold at the accessor, not by luck.

    The loader leaves _files empty on refusal today, so the guard in role_for
    is invisible to every other test. A later change that carried partial data
    into an INVALID result — to report what it saw, say — would start leaking
    roles silently. Pin the invariant on the accessor itself.
    """
    from review_engine.context_evidence import ReviewContextResult

    entries = {"review_engine/router.py": {"role": "review engine"}}

    for status in (INVALID, MISSING):
        result = ReviewContextResult(status=status, reasons=["schema-mismatch"], _files=entries)

        assert result.usable is False
        assert result.role_for("review_engine/router.py") == ""
        assert result.entry_for("review_engine/router.py") == {}


def test_a_usable_result_does_hand_out_its_entries(tmp_path):
    """The counterpart, so the guard cannot be satisfied by always returning ''."""
    from review_engine.context_evidence import ReviewContextResult

    entries = {"review_engine/router.py": {"role": "review engine", "hub_score": 3}}

    for status in (VERIFIED, STALE):
        result = ReviewContextResult(status=status, _files=entries)

        assert result.role_for("review_engine/router.py") == "review engine"
        assert result.entry_for("review_engine/router.py")["hub_score"] == 3


# ── coverage must not flatter itself ─────────────────────────────────────────

def test_coverage_separates_entries_from_entries_with_a_role(tmp_path):
    """"286/286 files" reads as complete when a third say "unknown".

    The builder's role heuristics are path-based and match nothing for most of
    mq-mcp's own modules, so a full-coverage artifact can still tell the model
    nothing about them. Report both numbers.
    """
    repo = _repo(tmp_path)
    payload = _artifact()
    payload["files"]["docs/guide.md"]["role"] = "unknown"

    result = _load(tmp_path, payload, repo=repo)

    assert result.entry_count == 2
    assert result.roled_count == 1
    assert "286" not in "".join(result.provenance_lines())
    assert "2/2 files, 1 with a role" in "\n".join(result.provenance_lines())


def test_an_artifact_of_nothing_but_unknowns_says_so(tmp_path):
    payload = _artifact()
    for entry in payload["files"].values():
        entry["role"] = "unknown"

    result = _load(tmp_path, payload)

    assert result.roled_count == 0
    assert "0 with a role" in "\n".join(result.provenance_lines())
