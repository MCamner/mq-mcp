"""Exact-code binding tests for mq.review-receipt.v1."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator

from review_engine.review_receipt import (
    capture_subject,
    run_receipted_review,
    verify_receipt_id,
)


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "b.md").write_text("# B\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=repo,
        check=True,
    )
    return repo


def _producer() -> dict:
    return {
        "schema": "mq.runtime-identity.v1",
        "component": "mq-mcp",
        "version": "2.1.0",
        "commit": "a" * 40,
        "install_type": "editable",
        "identity_quality": "verified",
    }


def test_file_receipt_binds_commit_and_exact_file_bytes(tmp_path):
    repo = _git_repo(tmp_path)
    receipt = run_receipted_review(
        root=repo,
        kind="file",
        mode="comment",
        relative_path="a.py",
        producer=_producer(),
        run=lambda: "review result",
    )

    assert receipt["status"] == "ISSUED"
    assert receipt["subject"]["commit"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    assert receipt["subject"]["scope"]["path"] == "a.py"
    assert receipt["subject"]["scope"]["files"][0]["sha256"].startswith("sha256:")
    assert receipt["review"]["result"] == "review result"
    assert verify_receipt_id(receipt) is True


def test_dirty_source_can_still_be_exactly_bound(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")

    receipt = run_receipted_review(
        root=repo,
        kind="file",
        mode="comment",
        relative_path="a.py",
        producer=_producer(),
        run=lambda: "reviewed dirty bytes",
    )

    assert receipt["status"] == "ISSUED"
    assert receipt["subject"]["worktree_clean"] is False


def test_subject_change_during_review_refuses_receipt(tmp_path):
    repo = _git_repo(tmp_path)

    def mutate():
        (repo / "a.py").write_text("x = 999\n", encoding="utf-8")
        return "result from old snapshot"

    receipt = run_receipted_review(
        root=repo,
        kind="file",
        mode="comment",
        relative_path="a.py",
        producer=_producer(),
        run=mutate,
    )

    assert receipt["status"] == "REFUSED"
    assert receipt["reason"] == "subject-changed-during-review"
    assert receipt["stability"]["unchanged"] is False


def test_result_tampering_breaks_receipt_id(tmp_path):
    repo = _git_repo(tmp_path)
    receipt = run_receipted_review(
        root=repo,
        kind="file",
        mode="comment",
        relative_path="a.py",
        producer=_producer(),
        run=lambda: {"ok": True},
    )
    receipt["review"]["result"] = {"ok": False}
    assert verify_receipt_id(receipt) is False


def test_diff_scope_tracks_only_reviewable_changed_files(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "b.md").write_text("# changed\n", encoding="utf-8")
    (repo / "note.txt").write_text("untracked and not reviewed\n", encoding="utf-8")

    subject = capture_subject(repo, kind="diff")
    paths = [item["path"] for item in subject["scope"]["files"]]
    assert paths == ["a.py", "b.md"]
    assert "note.txt" not in paths


def test_repo_scope_is_python_source_tree_not_git_or_venv(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "c.py").write_text("y = 1\n", encoding="utf-8")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "hidden.py").write_text("secret = 1\n", encoding="utf-8")

    subject = capture_subject(repo, kind="repo")
    paths = [item["path"] for item in subject["scope"]["files"]]
    assert "a.py" in paths
    assert "pkg/c.py" in paths
    assert ".venv/hidden.py" not in paths


def test_non_git_subject_is_refused_not_guessed(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")

    receipt = run_receipted_review(
        root=root,
        kind="file",
        mode="comment",
        relative_path="a.py",
        producer=_producer(),
        run=lambda: "review",
    )

    assert receipt["status"] == "REFUSED"
    assert receipt["reason"] == "subject-commit-unavailable"


def test_receipt_matches_schema(tmp_path):
    repo = _git_repo(tmp_path)
    receipt = run_receipted_review(
        root=repo,
        kind="file",
        mode="comment",
        relative_path="a.py",
        producer=_producer(),
        run=lambda: {"ok": True, "findings": []},
    )
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "review_receipt.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(receipt)
