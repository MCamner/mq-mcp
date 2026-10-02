"""Server wiring for optional review receipts without OpenAI calls."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_receipt", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)


def _fake_receipt(**kwargs):
    return {
        "schema": "mq.review-receipt.v1",
        "status": "ISSUED",
        "kind": kwargs["kind"],
        "mode": kwargs["mode"],
        "root": str(kwargs["root"]),
        "relative_path": kwargs.get("relative_path"),
    }


def test_review_file_receipt_routes_through_exact_subject_wrapper(monkeypatch, tmp_path):
    repo = tmp_path / "ext"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(server, "resolve_allowed_local_file", lambda p: repo)
    monkeypatch.setattr(server, "_run_with_review_receipt", _fake_receipt)

    result = server.review_file(
        "a.py",
        mode="comment",
        repo_path=str(repo),
        receipt=True,
    )

    assert result["schema"] == "mq.review-receipt.v1"
    assert result["kind"] == "file"
    assert result["root"] == str(repo.resolve())
    assert result["relative_path"] == "a.py"


def test_review_diff_receipt_uses_mq_mcp_review_root(monkeypatch):
    monkeypatch.setattr(server, "_run_with_review_receipt", _fake_receipt)

    result = server.review_diff(mode="architecture", receipt=True)

    assert result["kind"] == "diff"
    assert result["mode"] == "architecture"
    assert result["root"] == str(ROOT.resolve())


def test_review_repo_receipt_uses_external_review_root(monkeypatch, tmp_path):
    repo = tmp_path / "repo-signal"
    repo.mkdir()
    monkeypatch.setattr(server, "resolve_allowed_local_file", lambda p: repo)
    monkeypatch.setattr(server, "_run_with_review_receipt", _fake_receipt)

    result = server.review_repo(
        mode="comment",
        max_files=3,
        repo_path=str(repo),
        receipt=True,
    )

    assert result["kind"] == "repo"
    assert result["root"] == str(repo.resolve())


def test_risk_review_file_supports_receipt(monkeypatch):
    monkeypatch.setattr(server, "_run_with_review_receipt", _fake_receipt)

    result = server.risk_review_file("mq-mcp/server.py", mode="security", receipt=True)

    assert result["kind"] == "file"
    assert result["mode"] == "risk:security"


def test_risk_review_diff_supports_receipt(monkeypatch):
    monkeypatch.setattr(server, "_run_with_review_receipt", _fake_receipt)

    result = server.risk_review_diff(mode="risk", receipt=True)

    assert result["kind"] == "diff"
    assert result["mode"] == "risk:risk"


def test_receipt_false_preserves_existing_review_file_signature_path(monkeypatch, tmp_path):
    repo = tmp_path / "ext"
    repo.mkdir()
    (repo / "missing.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(server, "resolve_allowed_local_file", lambda p: repo)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = server.review_file(
        "missing.py",
        repo_path=str(repo),
        receipt=False,
    )

    assert isinstance(result, str)
    assert "OPENAI_API_KEY" in result
