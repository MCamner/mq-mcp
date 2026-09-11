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


def test_load_lessons_filters_by_repo_and_query(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "mq-mcp", "risk": "medium", "summary": "update bridge tests after CLI flag changes"},
        {"repo": "mq-agent", "risk": "high", "summary": "keep route contracts synchronized"},
        {"risk": "medium", "summary": "general release hygiene"},
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons(
        repo="mq-mcp",
        query="bridge",
    )

    assert "update bridge tests" in out
    assert "route contracts" not in out
    assert "general release hygiene" not in out


def test_load_lessons_empty_when_no_store(monkeypatch, tmp_path):
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", tmp_path / "missing.jsonl")
    assert BridgetContext(path=tmp_path / "ctx.md").load_lessons() == ""


# --- Phase 4: REPL session metadata -----------------------------------------


def _ctx(tmp_path):
    return BridgetContext(
        path=tmp_path / "ctx.md", history_path=tmp_path / "history.jsonl"
    )


def test_record_chat_mode_writes_repl_metadata_and_markdown(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.record(
        "last prompt",
        ["t1", "t2"],
        "final answer",
        project="mq-mcp",
        branch="main",
        turns=4,
        duration_s=12.5,
        do_mode=True,
        chat_mode=True,
    )

    entry = json.loads(
        (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert entry["chat_mode"] is True
    assert entry["do_mode"] is True
    assert entry["turns"] == 4
    assert entry["duration_s"] == 12.5
    assert entry["project"] == "mq-mcp"
    # The rolling markdown block labels itself as a REPL session with turn count.
    md = (tmp_path / "ctx.md").read_text(encoding="utf-8")
    assert "Type: REPL session, 4 turns" in md


def test_record_one_shot_keeps_flat_shape(tmp_path):
    # One-shot callers leave the Phase-4 fields at defaults: no REPL keys leak
    # into the history line and the markdown block carries no REPL label.
    ctx = _ctx(tmp_path)
    ctx.record("p", [], "a", project="mq-mcp")

    entry = json.loads(
        (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert "chat_mode" not in entry
    assert "turns" not in entry
    assert "do_mode" not in entry
    assert "duration_s" not in entry
    assert "REPL session" not in (tmp_path / "ctx.md").read_text(encoding="utf-8")


def test_record_writes_daily_session_log(monkeypatch, tmp_path):
    monkeypatch.setattr(bridget_context, "SESSION_DIR", tmp_path / "sessions")
    ctx = _ctx(tmp_path)

    ctx.record("p", [], "a")

    daily = list((tmp_path / "sessions").glob("*.jsonl"))
    assert len(daily) == 1
    assert json.loads(daily[0].read_text(encoding="utf-8"))["summary"] == "a"


def test_load_injects_only_three_bounded_recent_sessions(tmp_path):
    ctx = _ctx(tmp_path)
    for i in range(5):
        ctx.record(f"prompt {i}", [], "x" * 800)

    out = ctx.load()

    assert "temporary context only" in out
    assert out.count("Temporary context: yes") == 3
    assert "x" * 650 not in out


def test_forget_day_removes_history_daily_and_context(monkeypatch, tmp_path):
    monkeypatch.setattr(bridget_context, "SESSION_DIR", tmp_path / "sessions")
    ctx = _ctx(tmp_path)
    ctx.record("p1", [], "a1")
    date = ctx.read_history(limit=1)[0]["ts"][:10]

    removed = ctx.forget_day(date)

    assert removed == 1
    assert ctx.read_history(limit=0) == []
    assert not list((tmp_path / "sessions").glob("*.jsonl"))
    assert not (tmp_path / "ctx.md").exists()


def test_metrics_are_derived_from_history(tmp_path):
    ctx = BridgetContext(
        path=tmp_path / "ctx.md",
        history_path=tmp_path / "history.jsonl",
        metrics_path=tmp_path / "metrics.json",
    )
    ctx.record("p", ["git_status"], "learning suggestion", turns=2, chat_mode=True)

    metrics = ctx.metrics()

    assert metrics["totals"]["sessions"] == 1
    assert metrics["totals"]["chat_sessions"] == 1
    assert metrics["totals"]["tool_calls"] == 1
    assert metrics["totals"]["learning_suggestions"] == 1
    assert metrics["totals"]["accepted_learning"] >= 0
    assert (tmp_path / "metrics.json").exists()
