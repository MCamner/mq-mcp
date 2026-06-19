"""Repo-namespacing for review memory + cross-repo learn/review validation.

Covers the data-layer (ReviewMemory namespaced by repo, backward-compatible
migration) and the no-OpenAI validation paths of review_file / learn_from_review
/ learn_extract_from_last_review with repo_path.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make review_engine importable
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_ns", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # also puts REPO_ROOT on sys.path

from review_engine.review_memory import ReviewMemory, DEFAULT_REPO  # noqa: E402

review_file = _mod.review_file
learn_from_review = _mod.learn_from_review
learn_extract_from_last_review = _mod.learn_extract_from_last_review


def _mem(tmp_path) -> ReviewMemory:
    return ReviewMemory(history_file=tmp_path / "review_history.json")


# ── ReviewMemory namespacing ────────────────────────────────────────────────

def test_repo_isolation_same_path_no_collision(tmp_path):
    m = _mem(tmp_path)
    m.save("tools/x.py", "comment", "A finding", 1, {"NOTE": 1}, repo="repo-signal")
    m.save("tools/x.py", "comment", "B finding", 2, {"NOTE": 2}, repo="mq-hal")

    a = m.get_last("tools/x.py", repo="repo-signal")
    b = m.get_last("tools/x.py", repo="mq-hal")
    assert a.findings_text == "A finding" and a.finding_count == 1
    assert b.findings_text == "B finding" and b.finding_count == 2
    # No cross-repo bleed.
    assert m.get_last("tools/x.py", repo="other") is None


def test_default_repo_when_none(tmp_path):
    m = _mem(tmp_path)
    m.save("a.py", "comment", "x", 0, {})  # repo=None
    assert m.get_last("a.py") is not None
    assert m.get_last("a.py", repo=DEFAULT_REPO) is not None
    assert m.get_last_timestamp("a.py", repo=DEFAULT_REPO) > 0


def test_get_last_timestamp_repo_aware(tmp_path):
    m = _mem(tmp_path)
    m.save("p.py", "comment", "x", 0, {}, repo="repo-signal")
    assert m.get_last_timestamp("p.py", repo="repo-signal") > 0
    assert m.get_last_timestamp("p.py", repo="mq-hal") == 0.0


def test_legacy_flat_store_migrates_to_default_repo(tmp_path):
    # Write a legacy flat store ({path: [entries]}) and confirm it reads as mq-mcp.
    legacy = {
        "server.py": [{
            "file_path": "server.py", "mode": "comment", "timestamp": 1.0,
            "timestamp_iso": "2026-01-01T00:00:00Z", "model": "", "finding_count": 1,
            "severity_counts": {"NOTE": 1}, "findings_text": "legacy", "skill": "",
        }]
    }
    hf = tmp_path / "review_history.json"
    hf.write_text(json.dumps(legacy), encoding="utf-8")
    m = ReviewMemory(history_file=hf)
    assert m.get_last("server.py", repo=DEFAULT_REPO) is not None
    assert m.get_last("server.py").findings_text == "legacy"
    # A new save preserves the migrated legacy data under the default repo.
    m.save("new.py", "comment", "n", 0, {})
    reloaded = ReviewMemory(history_file=hf)
    assert reloaded.get_last("server.py", repo=DEFAULT_REPO) is not None
    assert reloaded.get_last("new.py", repo=DEFAULT_REPO) is not None


# ── cross-repo validation (no OpenAI, no lesson writes) ─────────────────────

def test_review_file_bad_repo_path_outside_allowlist_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("MQ_MCP_ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("MQ_MCP_LOCAL_REPOS", raising=False)
    out = review_file("x.py", repo_path=str(tmp_path / "outside"))
    assert out.startswith("review_file failed:")


def test_review_file_repo_path_not_dir_fails(monkeypatch, tmp_path):
    f = tmp_path / "f.py"
    f.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    out = review_file("x.py", repo_path=str(f))
    assert out.startswith("review_file failed:")
    assert "not a directory" in out


def test_learn_from_review_outside_allowlist_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("MQ_MCP_ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("MQ_MCP_LOCAL_REPOS", raising=False)
    out = learn_from_review("x.py", repo_path=str(tmp_path / "nope"))
    assert out.startswith("learn_from_review failed:")


def test_learn_from_review_no_history_names_repo(monkeypatch, tmp_path):
    repo = tmp_path / "repo-signal"
    repo.mkdir()
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    out = learn_from_review("totally/unique/nope.py", repo_path=str(repo))
    assert "No review history found" in out
    assert "repo-signal" in out


def test_learn_extract_outside_allowlist_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("MQ_MCP_ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("MQ_MCP_LOCAL_REPOS", raising=False)
    out = learn_extract_from_last_review("x.py", repo_path=str(tmp_path / "nope"))
    assert out.startswith("learn_extract_from_last_review failed:")
