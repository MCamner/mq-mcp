"""Provenance fields of architecture_map.v1 must survive being checked.

ADR-008 makes generated/architecture/architecture_map.json the canonical
review-context evidence and lets a loader refuse it on identity grounds.
Two fields carry that weight and both had a way of being wrong:

  repo_name     was the directory name, which is the worktree in a worktree
  generated_at  is honest when build_repo_context() runs the builder first,
                but the flat_arch_map=None branch stamped a disk-read map
                with the current time

These tests pin both to something a validator can trust.
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

from review_engine.generated_artifacts import (  # noqa: E402
    ARCHITECTURE_MAP_SCHEMA,
    build_rich_architecture_map,
)


def _repo(tmp_path: Path, *, repo_dir_name: str = "checkout", contract: str | None = None) -> Path:
    """A minimal repo the builder can scan."""
    repo = tmp_path / repo_dir_name
    (repo / "review_engine").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "review_engine" / "router.py").write_text("def route():\n    pass\n", encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    if contract is not None:
        (repo / ".mq").mkdir()
        (repo / ".mq" / "repo-contract.json").write_text(contract, encoding="utf-8")
    return repo


def _build(repo: Path, tmp_path: Path, **kwargs) -> dict:
    return build_rich_architecture_map(
        repo_root=repo,
        out_dir=tmp_path / "out",
        **kwargs,
    )


# ── repo_name ────────────────────────────────────────────────────────────────

def test_repo_name_comes_from_the_repo_contract_not_the_directory(tmp_path):
    """A worktree's directory is not the repo. The contract is."""
    repo = _repo(tmp_path, repo_dir_name="mq-mcp-review-context",
                 contract='{"repo": "mq-mcp"}')

    result = _build(repo, tmp_path)

    assert result["repo_name"] == "mq-mcp"
    assert result["repo_name"] != repo.name


def test_repo_name_falls_back_to_the_directory_without_a_contract(tmp_path):
    repo = _repo(tmp_path, repo_dir_name="some-repo")

    assert _build(repo, tmp_path)["repo_name"] == "some-repo"


@pytest.mark.parametrize(
    "contract",
    [
        "{ not json",
        "[]",
        '{"repo": ""}',
        '{"repo": 7}',
        '{"role": "runtime"}',
    ],
    ids=["malformed", "not-an-object", "empty", "not-a-string", "no-repo-key"],
)
def test_unusable_contract_falls_back_rather_than_raising(tmp_path, contract):
    """A broken contract must not take the whole build down."""
    repo = _repo(tmp_path, repo_dir_name="fallback-repo", contract=contract)

    assert _build(repo, tmp_path)["repo_name"] == "fallback-repo"


# ── generated_at ─────────────────────────────────────────────────────────────

def test_generated_at_describes_a_scan_that_actually_ran(tmp_path):
    """The stale-map-on-disk branch must scan, not inherit.

    A flat map left on disk claims a file that no longer exists and omits
    every file that does. Stamping that with the current time would present
    an old scan as a new one.
    """
    repo = _repo(tmp_path)
    ctx = repo / "review_engine" / "context"
    ctx.mkdir(parents=True)
    (ctx / "architecture_map.json").write_text(
        json.dumps({"deleted/ghost.py": "review engine — context building and routing"}),
        encoding="utf-8",
    )

    result = _build(repo, tmp_path)

    assert "deleted/ghost.py" not in result["files"]
    assert "review_engine/router.py" in result["files"]
    assert result["file_count"] == len(result["files"])


def test_generated_at_is_recent_and_utc(tmp_path):
    before = datetime.now(timezone.utc)
    result = _build(_repo(tmp_path), tmp_path)
    after = datetime.now(timezone.utc)

    stamped = datetime.fromisoformat(result["generated_at"])

    assert stamped.tzinfo is not None
    assert stamped.utcoffset() == timedelta(0)
    assert before <= stamped <= after


def test_an_explicit_flat_map_is_still_honored(tmp_path):
    """build_repo_context() hands over the map it just built. Keep that path."""
    repo = _repo(tmp_path)

    result = _build(repo, tmp_path, flat_arch_map={"review_engine/router.py": "handed over"})

    assert list(result["files"]) == ["review_engine/router.py"]
    assert result["files"]["review_engine/router.py"]["role"] == "handed over"


def test_an_explicit_empty_flat_map_is_not_treated_as_absent(tmp_path):
    """{} is a caller saying 'nothing'. None is a caller saying 'you decide'."""
    repo = _repo(tmp_path)

    result = _build(repo, tmp_path, flat_arch_map={})

    assert result["files"] == {}
    assert result["file_count"] == 0


# ── the envelope a loader will check ─────────────────────────────────────────

def test_written_artifact_carries_the_full_envelope(tmp_path):
    repo = _repo(tmp_path, repo_dir_name="wt", contract='{"repo": "mq-mcp"}')

    _build(repo, tmp_path)
    written = json.loads((tmp_path / "out" / "architecture_map.json").read_text(encoding="utf-8"))

    assert written["schema"] == ARCHITECTURE_MAP_SCHEMA
    assert written["repo_name"] == "mq-mcp"
    assert written["file_count"] == len(written["files"])
    assert datetime.fromisoformat(written["generated_at"]).tzinfo is not None
    for entry in written["files"].values():
        assert set(entry) == {"role", "public_symbols", "last_review_timestamp", "hub_score"}


def test_ownership_map_reports_the_same_repo_identity(tmp_path):
    """Sibling artifact, same field, same meaning — or a loader cannot trust it."""
    from review_engine.generated_artifacts import build_ownership_map

    repo = _repo(tmp_path, repo_dir_name="wt", contract='{"repo": "mq-mcp"}')

    assert build_ownership_map(repo_root=repo, out_dir=tmp_path / "own")["repo_name"] == "mq-mcp"


# ── the scan the enrichment now depends on ───────────────────────────────────

def _scannable(tmp_path: Path) -> Path:
    """A repo carrying one of everything the builder is supposed to skip."""
    from review_engine.repo_context_builder import IGNORED_DIRS

    repo = tmp_path / "scan-repo"
    (repo / "review_engine").mkdir(parents=True)
    (repo / "review_engine" / "router.py").write_text("x = 1\n", encoding="utf-8")

    for ignored in IGNORED_DIRS:
        d = repo / ignored
        d.mkdir(parents=True, exist_ok=True)
        (d / "junk.py").write_text("x = 1\n", encoding="utf-8")

    (repo / ".env").write_text("K=v\n", encoding="utf-8")
    (repo / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (repo / ".hidden").write_text("skip me\n", encoding="utf-8")

    deep = repo / "a" / "b" / "c" / "d" / "e" / "f"
    deep.mkdir(parents=True)
    (deep / "too_deep.py").write_text("x = 1\n", encoding="utf-8")

    return repo


def test_scan_applies_the_builders_exclusion_rules(tmp_path):
    from review_engine.repo_context_builder import IGNORED_DIRS, scan_architecture_map

    mapped = scan_architecture_map(_scannable(tmp_path))

    assert "review_engine/router.py" in mapped
    for ignored in IGNORED_DIRS:
        assert f"{ignored}/junk.py" not in mapped, f"{ignored}/ was scanned"
    assert ".hidden" not in mapped
    assert ".env" in mapped and ".gitignore" in mapped
    assert "a/b/c/d/e/f/too_deep.py" not in mapped


def test_build_context_and_scan_agree(tmp_path):
    """build_context delegates to the scan. Pin that they stay the same map."""
    from review_engine.repo_context_builder import build_context, scan_architecture_map

    repo = _scannable(tmp_path)

    built = build_context(repo_root=repo, out_dir=tmp_path / "ctx")["architecture_map"]

    assert built == scan_architecture_map(repo)


def test_enrichment_without_a_handed_over_map_excludes_the_same_paths(tmp_path):
    """The regression that matters: the scan behind generated_at must not widen."""
    repo = _scannable(tmp_path)

    files = _build(repo, tmp_path)["files"]

    assert "review_engine/router.py" in files
    assert "__pycache__/junk.py" not in files
    assert ".git/junk.py" not in files
