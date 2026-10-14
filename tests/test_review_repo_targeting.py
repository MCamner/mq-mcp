"""Targeting and isolation tests for review_repo.

These exercise repo resolution, file discovery, and the no-silent-fallback
contract WITHOUT calling OpenAI: review_file is monkeypatched to echo the
relative path it was handed so we can assert which root it resolved against.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_review_repo", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

review_repo = _mod.review_repo
resolve_repo_file = _mod.resolve_repo_file


def _make_repo(base: Path, name: str, files: list[str]) -> Path:
    repo = base / name
    repo.mkdir()
    for rel in files:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n", encoding="utf-8")
    return repo


@pytest.fixture
def echo_review_file(monkeypatch):
    """Replace review_file with a probe that records the resolved absolute path."""
    # review_repo refuses to run without a key; the probe never calls OpenAI.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    seen: list[Path] = []

    def _fake_review_file(relative_path, mode="comment", deep=False, repo_path=None):
        # Mirror real review_file: confine resolution to the external repo via
        # the review-root ContextVar for the duration of the lookup.
        if repo_path is not None:
            root = _mod.resolve_allowed_local_file(repo_path)
            tok = _mod._REVIEW_ROOT.set(root)
            try:
                resolved = resolve_repo_file(relative_path)
            finally:
                _mod._REVIEW_ROOT.reset(tok)
        else:
            resolved = resolve_repo_file(relative_path)
        seen.append(resolved)
        return f"OK {relative_path}"

    monkeypatch.setattr(_mod, "review_file", _fake_review_file)
    return seen


# A. Backward compatibility — no repo_path reviews mq-mcp itself.
def test_no_path_reviews_self(echo_review_file):
    out = review_repo(max_files=1)
    assert "review_repo:" in out
    assert echo_review_file, "expected at least one file reviewed"
    for p in echo_review_file:
        assert str(p).startswith(str(ROOT.resolve()))


# B. Valid external repo path — reviewed files live under the target.
def test_external_repo_reviewed(echo_review_file, monkeypatch, tmp_path):
    target = _make_repo(tmp_path, "repo-signal", ["src/a.py", "src/b.py"])
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    out = review_repo(repo_path=str(target), max_files=5)
    assert "repo=repo-signal" in out
    # Output carries the full review root so downstream can verify targeting.
    assert f"review_root={target.resolve()}" in out
    assert echo_review_file
    for p in echo_review_file:
        assert str(p).startswith(str(target.resolve()))
        assert "mq-mcp" not in str(p.relative_to(target.resolve()))


def test_structured_repo_review_reports_complete_measured_coverage(
    echo_review_file, monkeypatch, tmp_path
):
    target = _make_repo(tmp_path, "complete-repo", ["a.py", "b.py"])
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))

    out = review_repo(repo_path=str(target), max_files=5, structured=True)

    assert out["ok"] is True
    assert isinstance(out["review"], str)
    assert out["completeness"] == {
        "status": "complete",
        "steps": [
            {
                "step": 1,
                "status": "complete",
                "source_item_count": 2,
                "executed_call_count": 2,
            }
        ],
    }


def test_structured_repo_review_reports_partial_when_file_cap_truncates(
    echo_review_file, monkeypatch, tmp_path
):
    target = _make_repo(tmp_path, "partial-repo", ["a.py", "b.py", "c.py"])
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))

    out = review_repo(repo_path=str(target), max_files=2, structured=True)

    assert out["ok"] is True
    assert out["completeness"] == {
        "status": "partial",
        "steps": [
            {
                "step": 1,
                "status": "partial",
                "source_item_count": 3,
                "executed_call_count": 2,
            }
        ],
    }


# C. Missing path — clear failure, no fallback.
def test_missing_path_fails(echo_review_file, monkeypatch, tmp_path):
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    missing = tmp_path / "does-not-exist"
    out = review_repo(repo_path=str(missing))
    assert out.startswith("review_repo failed:")
    assert "not found" in out
    assert echo_review_file == []


# D. File instead of directory.
def test_file_path_fails(echo_review_file, monkeypatch, tmp_path):
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    f = tmp_path / "thing.py"
    f.write_text("x = 1\n", encoding="utf-8")
    out = review_repo(repo_path=str(f))
    assert out.startswith("review_repo failed:")
    assert "not a directory" in out
    assert echo_review_file == []


# E. Outside allowlist — blocked, no fallback.
def test_outside_allowlist_fails(echo_review_file, monkeypatch, tmp_path):
    monkeypatch.delenv("MQ_MCP_ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("MQ_MCP_LOCAL_REPOS", raising=False)
    target = _make_repo(tmp_path, "secret-repo", ["a.py"])
    out = review_repo(repo_path=str(target))
    assert out.startswith("review_repo failed:")
    assert "outside allowed roots" in out.lower() or "blocked" in out.lower()
    assert echo_review_file == []


# F/G. Evidence paths are target-relative, never mq-mcp; bad path never reviews self.
def test_no_silent_self_fallback(echo_review_file, monkeypatch, tmp_path):
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    bogus = tmp_path / "nope"
    out = review_repo(repo_path=str(bogus))
    assert "review_repo:" not in out.split("\n")[0] or "not found" in out
    # crucially, no file under mq-mcp was reviewed
    assert echo_review_file == []


# Contextvar restored after a call (no leak into subsequent self-review).
def test_review_root_restored_after_external(echo_review_file, monkeypatch, tmp_path):
    target = _make_repo(tmp_path, "ext", ["a.py"])
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    review_repo(repo_path=str(target), max_files=1)
    # After the external review, a self-review resolves back under mq-mcp.
    echo_review_file.clear()
    review_repo(max_files=1)
    for p in echo_review_file:
        assert str(p).startswith(str(ROOT.resolve()))


# F. Fail closed when no review can actually run.
#
# Without OPENAI_API_KEY every per-file review returned "requires
# OPENAI_API_KEY", yet review_repo reported "N file(s) reviewed" and a caller
# recorded the run as a success. The precondition is checked before the
# receipt branch and the file loop, so neither a review text nor an ISSUED
# receipt can claim a review that never happened.
@pytest.mark.parametrize("value", [None, ""])
def test_missing_api_key_fails_before_any_file_review(monkeypatch, value):
    calls: list[str] = []
    monkeypatch.setattr(
        _mod, "review_file", lambda path, **_kw: calls.append(path) or "OK"
    )
    if value is None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENAI_API_KEY", value)

    out = review_repo(max_files=1)

    assert out == "review_repo failed: OPENAI_API_KEY is required"
    assert calls == []


def test_missing_api_key_issues_no_receipt(monkeypatch, tmp_path):
    target = _make_repo(tmp_path, "repo-signal", ["a.py"])
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    receipts: list[object] = []
    monkeypatch.setattr(
        _mod, "_run_with_review_receipt", lambda **kw: receipts.append(kw) or {}
    )

    out = review_repo(repo_path=str(target), receipt=True)

    assert out == "review_repo failed: OPENAI_API_KEY is required"
    assert receipts == []
