"""Behavioral regression tests for the optional risk_review_repo MCP tool."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq-mcp"))
import server


def test_invalid_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    assert "mode must be" in server.risk_review_repo(mode="comment")


def test_missing_key_does_not_claim_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert server.risk_review_repo() == "risk_review_repo failed: OPENAI_API_KEY is required"


def test_unapproved_checkout_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    def deny(_path: str | None) -> Path:
        raise ValueError("not allowlisted")
    monkeypatch.setattr(server, "_receipt_review_root", deny)
    assert "not allowlisted" in server.risk_review_repo(repo_path="/unexpected")


def test_repo_scope_reviews_only_bounded_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    for index in range(7):
        (tmp_path / f"f{index}.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / ".hidden.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(server, "_receipt_review_root", lambda _path: tmp_path)
    reviewed: list[str] = []
    def fake_file(path: str, mode: str, receipt: bool = False) -> str:
        reviewed.append(path)
        assert server._REVIEW_ROOT.get() == tmp_path
        return "reviewed"
    monkeypatch.setattr(server, "risk_review_file", fake_file)
    result = server.risk_review_repo(mode="risk", repo_path=str(tmp_path))
    assert result.startswith("risk_review_repo: 5 file(s) reviewed  mode=risk")
    assert "[capped at 5]" in result
    assert reviewed == [f"f{i}.py" for i in range(5)]


def test_file_failure_does_not_claim_repo_review(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    (tmp_path / "a.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(server, "_receipt_review_root", lambda _path: tmp_path)
    monkeypatch.setattr(
        server, "risk_review_file",
        lambda *_args, **_kwargs: "risk_review_file failed: API unavailable",
    )
    assert server.risk_review_repo().startswith("risk_review_repo failed:")
