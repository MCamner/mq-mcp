import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import bridget_context
from bridget_context import BridgetContext


def _write_lessons(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_load_lessons_filters_risk_and_formats(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "a", "risk": "low", "summary": "low risk noise"},
        {"repo": "b", "risk": "medium", "summary": "medium lesson one"},
        {"repo": "c", "risk": "high", "summary": "high lesson two"},
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons()
    assert "Lessons learned" in out
    assert "[b] medium lesson one" in out
    assert "[c] high lesson two" in out
    assert "low risk noise" not in out  # low-risk excluded


def test_load_lessons_dedupes_paraphrases(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "x", "risk": "medium",
         "summary": "Run git diff on the last contract commit and grep mcp.tool to document new tools in the contract table"},
        {"repo": "x", "risk": "medium",
         "summary": "Run git diff on the last contract commit and grep mcp.tool to document new tools in the contract table now"},
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons()
    assert out.count("\n- ") == 1  # the near-identical paraphrase is collapsed


def test_load_lessons_empty_when_no_store(monkeypatch, tmp_path):
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", tmp_path / "missing.jsonl")
    assert BridgetContext(path=tmp_path / "ctx.md").load_lessons() == ""
