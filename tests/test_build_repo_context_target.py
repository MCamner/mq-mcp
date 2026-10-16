"""build_repo_context(repo_path=...) writes review evidence for another repo.

The review itself never writes (ADR-008). This explicit step is the only way
another repo gets generated/architecture/, so it must stay inside the
allowlist, write nothing but the two gitignored artifacts, and refuse a repo
where they would show up as changes to commit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq-mcp"))
import server

from review_engine.context_evidence import VERIFIED, load_review_context, repo_identity


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture
def target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "other-repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "core.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (repo / "README.md").write_text("# other\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    monkeypatch.setattr(server, "_receipt_review_root", lambda _path: repo.resolve())
    return repo


def _ignore_generated(repo: Path) -> None:
    (repo / "generated").mkdir(exist_ok=True)
    (repo / "generated" / ".gitignore").write_text("*.json\n", encoding="utf-8")
    _git(repo, "add", "generated/.gitignore")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "ignore")


def test_refuses_repo_where_artifacts_are_not_gitignored(target: Path) -> None:
    result = server.build_repo_context(repo_path=str(target))
    assert result.startswith("build_repo_context blocked:")
    assert "not gitignored" in result
    assert not (target / "generated").exists()


def test_outside_allowlist_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(_path: str | None) -> Path:
        raise ValueError("not allowlisted")
    monkeypatch.setattr(server, "_receipt_review_root", deny)
    assert server.build_repo_context(repo_path="/unexpected") == (
        "build_repo_context failed: not allowlisted"
    )


def test_refuses_a_directory_that_is_not_a_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setattr(server, "_receipt_review_root", lambda _path: plain)
    assert server.build_repo_context(repo_path=str(plain)).startswith("build_repo_context blocked:")
    assert not (plain / "generated").exists()


def test_writes_only_gitignored_artifacts_and_they_verify(target: Path) -> None:
    _ignore_generated(target)
    result = server.build_repo_context(repo_path=str(target))
    assert result.startswith("build_repo_context: other-repo")
    assert _git(target, "status", "--porcelain") == ""
    written = sorted(p.name for p in (target / "generated" / "architecture").iterdir())
    assert written == ["architecture_map.json", "ownership_map.json"]
    assert not (target / "review_engine").exists()

    loaded = load_review_context(
        target / "generated" / "architecture" / "architecture_map.json",
        repo_root=target, expected_repo=repo_identity(target),
    )
    assert loaded.status == VERIFIED
    assert loaded.entry_count == loaded.scanned_count == 2


def test_tracked_artifact_is_not_overwritten(target: Path) -> None:
    out = target / "generated" / "architecture"
    out.mkdir(parents=True)
    (out / "architecture_map.json").write_text("{}\n", encoding="utf-8")
    _ignore_generated(target)
    _git(target, "add", "-f", "generated/architecture/architecture_map.json")
    _git(target, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "track")
    assert server.build_repo_context(repo_path=str(target)).startswith("build_repo_context blocked:")
    assert (out / "architecture_map.json").read_text(encoding="utf-8") == "{}\n"
