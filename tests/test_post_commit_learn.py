import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "post_commit_learn", ROOT / "scripts" / "post_commit_learn.py"
)
pcl = importlib.util.module_from_spec(_spec)
sys.modules["post_commit_learn"] = pcl
_spec.loader.exec_module(pcl)


def _redirect_files(monkeypatch, tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    lessons = tmp_path / "lessons.jsonl"
    monkeypatch.setattr(pcl, "INBOX_FILE", inbox)
    monkeypatch.setattr(pcl, "LESSONS_FILE", lessons)
    monkeypatch.setattr(pcl, "LOG_FILE", tmp_path / "post-commit.log")
    return inbox, lessons


def test_append_inbox_writes_pending_record(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    pcl.append_inbox(
        {"pattern_name": "p", "summary": "s", "confidence": "high", "evidence": ["e"]},
        "abc123def456",
    )
    rec = json.loads(inbox.read_text().strip())
    assert rec["status"] == "pending"
    assert rec["source"] == "post-commit"
    assert rec["commit"] == "abc123def456"[:12]
    assert rec["confidence"] == "high"


def test_is_duplicate_detects_paraphrase(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    existing = [pcl._words("run git diff and grep mcp tool to document new tools")]
    near = {"summary": "run git diff and grep mcp tool to document new tools now"}
    far = {"summary": "battery status reads from system power management only"}
    assert pcl.is_duplicate(near, existing) is True
    assert pcl.is_duplicate(far, existing) is False
    assert pcl.is_duplicate({"summary": ""}, existing) is True  # empty == drop


def test_run_skips_when_ollama_unavailable(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "unavailable", "reason": "model not found"}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    result = pcl.run()
    assert result.startswith("skip: ollama unavailable")
    assert not inbox.exists()


def test_run_skips_low_signal(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return "file.py — role"

        @staticmethod
        def learn_extract_pattern(_findings, approve=False, repo_context=""):
            return {"confidence": "low", "evidence": [], "pattern_name": "x"}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("sha1", "some diff"))
    result = pcl.run()
    assert result.startswith("skip: low-signal")
    assert not inbox.exists()


def test_run_queues_grounded_candidate(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return "file.py — role"

        @staticmethod
        def learn_extract_pattern(_findings, approve=False, repo_context=""):
            return {
                "confidence": "high",
                "evidence": ["file.py line 1"],
                "pattern_name": "version drift guard",
                "summary": "keep pyproject version in sync with VERSION",
            }

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("deadbeef", "diff"))
    result = pcl.run()
    assert result.startswith("queued:")
    rec = json.loads(inbox.read_text().strip())
    assert rec["pattern_name"] == "version drift guard"
    assert rec["status"] == "pending"
