"""The drift check for repo context asks whether the evidence is usable.

It used to compare the artifact's filesystem mtime against server.py's, which
answers whether one file is older than another — not whether the evidence is
current, complete, or even about this repo. ADR-008 puts the question on
generated/architecture/architecture_map.json and its declared generated_at.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import review_engine.drift_detector as dd  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mq-mcp"
    (repo / "mq-mcp").mkdir(parents=True)
    (repo / "mq-mcp" / "server.py").write_text("x = 1\n", encoding="utf-8")
    (repo / ".mq").mkdir()
    (repo / ".mq" / "repo-contract.json").write_text('{"repo": "mq-mcp"}', encoding="utf-8")
    return repo


def _artifact(repo: Path, **overrides) -> None:
    out = repo / "generated" / "architecture"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "architecture_map.v1",
        "repo_name": "mq-mcp",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 2,
        "files": {
            "mq-mcp/server.py": {"role": "MCP server", "public_symbols": [],
                                 "last_review_timestamp": None, "hub_score": 0},
            ".mq/repo-contract.json": {"role": "unknown", "public_symbols": [],
                                       "last_review_timestamp": None, "hub_score": 0},
        },
    }
    payload.update(overrides)
    (out / "architecture_map.json").write_text(json.dumps(payload), encoding="utf-8")


def _context_findings(tmp_path, monkeypatch, repo: Path):
    monkeypatch.setattr(dd, "REPO_ROOT", repo)
    findings = dd.DriftDetector().detect()
    return [f for f in findings if "architecture_map" in f.location]


def test_a_current_artifact_produces_no_context_finding(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _artifact(repo)

    assert _context_findings(tmp_path, monkeypatch, repo) == []


def test_a_missing_artifact_is_reported_with_the_fix(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    findings = _context_findings(tmp_path, monkeypatch, repo)

    assert len(findings) == 1
    assert findings[0].severity == "WARNING"
    assert "No repo-context evidence" in findings[0].description
    assert "build_repo_context" in findings[0].description
    # Absent is not the same as present-but-narrow. Saying "usable but
    # limited" about an artifact that does not exist would be a lie.
    assert "usable" not in findings[0].description


def test_a_stale_artifact_is_reported_with_its_age(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _artifact(repo, generated_at=(datetime.now(timezone.utc) - timedelta(days=108)).isoformat())

    findings = _context_findings(tmp_path, monkeypatch, repo)

    assert len(findings) == 1
    assert findings[0].severity == "WARNING"
    assert "stale" in findings[0].description


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"schema": "architecture_map.v2"}, "schema-mismatch"),
        ({"repo_name": "mq-agent"}, "repo-mismatch"),
        ({"files": "not a mapping"}, "files-malformed"),
    ],
    ids=["wrong-schema", "wrong-repo", "malformed-files"],
)
def test_a_refused_artifact_is_a_risk_naming_the_reason(tmp_path, monkeypatch, overrides, expected):
    """Unusable evidence sitting where review looks for it is worse than none."""
    repo = _repo(tmp_path)
    _artifact(repo, **overrides)

    findings = _context_findings(tmp_path, monkeypatch, repo)

    assert len(findings) == 1
    assert findings[0].severity == "RISK"
    assert expected in findings[0].description


def test_partial_coverage_is_reported(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _artifact(repo, files={"mq-mcp/server.py": {"role": "MCP server", "public_symbols": [],
                                                "last_review_timestamp": None, "hub_score": 0}})

    findings = _context_findings(tmp_path, monkeypatch, repo)

    assert len(findings) == 1
    assert findings[0].severity == "NOTE"
    assert "partial-coverage" in findings[0].description


def test_the_check_no_longer_depends_on_file_mtimes(tmp_path, monkeypatch):
    """Touching server.py must not, on its own, make the evidence stale."""
    repo = _repo(tmp_path)
    _artifact(repo)
    server = repo / "mq-mcp" / "server.py"
    future = datetime.now(timezone.utc) + timedelta(days=30)
    import os

    os.utime(server, (future.timestamp(), future.timestamp()))

    assert _context_findings(tmp_path, monkeypatch, repo) == []


def test_the_check_points_at_the_canonical_artifact(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    findings = _context_findings(tmp_path, monkeypatch, repo)

    assert findings[0].location == "generated/architecture/architecture_map.json"


def test_the_artifact_does_not_count_against_its_own_coverage(tmp_path, monkeypatch):
    """generated/ is build output. Scanning it would make coverage unreachable."""
    from review_engine.repo_context_builder import scan_architecture_map

    repo = _repo(tmp_path)
    _artifact(repo)

    mapped = scan_architecture_map(repo)

    assert "generated/architecture/architecture_map.json" not in mapped
