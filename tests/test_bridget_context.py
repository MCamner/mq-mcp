import json
import sys
from datetime import datetime
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


def test_load_lessons_filters_by_repo_risk_and_task(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "mq-mcp", "risk": "high", "lesson": "Validate MCP tool contracts after server changes", "tags": ["mcp", "contracts"]},
        {"repo": "mq-mcp", "risk": "low", "lesson": "Low risk MCP formatting detail", "tags": ["mcp"]},
        {"repo": "mq-hal", "risk": "high", "lesson": "Validate MCP tool contracts after server changes", "tags": ["mcp"]},
        {"repo": "mq-mcp", "risk": "high", "lesson": "Unrelated image palette guidance", "tags": ["images"]},
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons(
        repo="mq-mcp", task="update MCP server contract"
    )

    assert "Validate MCP tool contracts" in out
    assert "Low risk" not in out
    assert "mq-hal" not in out
    assert "palette" not in out


def test_load_lessons_matches_file_metadata(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "mq-mcp", "risk": "medium", "lesson": "Keep the generated catalog synchronized", "files_touched": ["mq-mcp/server.py"]},
        {"repo": "mq-mcp", "risk": "medium", "lesson": "Keep release notes concise", "files_touched": ["CHANGELOG.md"]},
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons(
        repo="mq-mcp", file_path="mq-mcp/server.py", task="change parser"
    )

    assert "generated catalog" in out
    assert "release notes" not in out


def test_load_lessons_bounds_complete_block(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "mq-mcp", "risk": "high", "lesson": f"contract lesson {i} " + "x" * 200}
        for i in range(10)
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons(
        repo="mq-mcp", task="contract", max_chars=500
    )

    assert out
    assert len(out) <= 500


def test_load_lessons_keeps_legacy_records_without_provenance(monkeypatch, tmp_path):
    store = tmp_path / "lessons.jsonl"
    _write_lessons(store, [
        {"repo": "mq-mcp", "risk": "high", "lesson": "Legacy contract lesson"}
    ])
    monkeypatch.setattr(bridget_context, "LESSONS_FILE", store)

    out = BridgetContext(path=tmp_path / "ctx.md").load_lessons(
        repo="mq-mcp", task="contract"
    )

    assert "Legacy contract lesson" in out


# --- Phase 4: REPL session metadata -----------------------------------------


def _ctx(tmp_path):
    return BridgetContext(
        path=tmp_path / "ctx.md", history_path=tmp_path / "history.jsonl"
    )


# --- Phase 2: bounded recent-session injection ------------------------------


def _write_history(path, entries):
    path.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n",
        encoding="utf-8",
    )


def test_load_injects_only_three_newest_recent_sessions(tmp_path):
    ctx = _ctx(tmp_path)
    _write_history(
        ctx.history_path,
        [
            {"ts": f"2026-08-{day:02d} 10:00", "prompt": f"prompt-{day}", "summary": f"summary-{day}"}
            for day in range(10, 15)
        ],
    )

    out = ctx.load(now=datetime(2026, 8, 14, 12, 0))

    assert out.count("## Session ") == 3
    assert "prompt-14" in out
    assert "prompt-13" in out
    assert "prompt-12" in out
    assert "prompt-11" not in out


def test_load_excludes_old_future_and_invalid_session_timestamps(tmp_path):
    ctx = _ctx(tmp_path)
    _write_history(
        ctx.history_path,
        [
            {"ts": "2026-08-07 12:00", "prompt": "boundary", "summary": "keep"},
            {"ts": "2026-08-07 11:59", "prompt": "too-old", "summary": "drop"},
            {"ts": "2026-08-14 12:01", "prompt": "future", "summary": "drop"},
            {"ts": "not-a-date", "prompt": "invalid", "summary": "drop"},
        ],
    )

    out = ctx.load(now=datetime(2026, 8, 14, 12, 0))

    assert "boundary" in out
    assert "too-old" not in out
    assert "future" not in out
    assert "invalid" not in out


def test_load_caps_each_rendered_session_at_500_chars(tmp_path):
    ctx = _ctx(tmp_path)
    _write_history(
        ctx.history_path,
        [
            {"ts": "2026-08-14 10:00", "prompt": "p" * 700, "summary": "s" * 700},
            {"ts": "2026-08-13 10:00", "prompt": "short", "summary": "short"},
        ],
    )

    out = ctx.load(now=datetime(2026, 8, 14, 12, 0))
    session_area = out.split("## Bridget session memory (previous sessions)\n\n", 1)[1]
    session_area = session_area.split("\n\nUse the above session history", 1)[0]
    blocks = session_area.split("\n\n")

    assert len(blocks) == 2
    assert all(len(block) <= 500 for block in blocks)


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


# --- Phase 2: date-partitioned temporary session logs -----------------------


def test_record_appends_one_daily_session_line(tmp_path):
    ctx = _ctx(tmp_path)

    ctx.record(
        "daily prompt",
        ["git_status"],
        "daily summary",
        project="mq-mcp",
        branch="main",
    )

    files = list((tmp_path / "bridget_memory" / "sessions").glob("*.jsonl"))
    assert len(files) == 1
    assert len(files[0].stem) == 10  # YYYY-MM-DD
    daily = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    legacy = [
        json.loads(line)
        for line in (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert daily == legacy
    assert daily[0]["summary"] == "daily summary"


def test_record_redacts_session_text_in_all_stores(tmp_path):
    ctx = _ctx(tmp_path)
    secret = "sk-" + "abcdefghijklmnopqrstuvwxyz0123456789"

    ctx.record(
        f"use token={secret}",
        ["run_tests"],
        f"password={secret}",
        project="mq-mcp",
    )

    daily_file = next((tmp_path / "bridget_memory" / "sessions").glob("*.jsonl"))
    combined = "\n".join(
        [
            daily_file.read_text(encoding="utf-8"),
            (tmp_path / "history.jsonl").read_text(encoding="utf-8"),
            (tmp_path / "ctx.md").read_text(encoding="utf-8"),
        ]
    )
    assert secret not in combined
    assert "<redacted>" in combined


def test_record_creates_only_declared_temporary_session_files(tmp_path):
    ctx = _ctx(tmp_path)

    ctx.record("prompt", ["git_status"], "summary", project="mq-mcp")

    created = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    daily = next(path for path in created if path.startswith("bridget_memory/sessions/"))
    assert created == {"ctx.md", "history.jsonl", daily}
    assert daily.endswith(".jsonl")


def test_daily_log_failure_does_not_block_legacy_history(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    ctx = BridgetContext(
        path=tmp_path / "ctx.md",
        history_path=tmp_path / "history.jsonl",
        sessions_dir=blocker / "sessions",
    )

    ctx.record("p", [], "a")

    assert len(ctx.read_history()) == 1


# --- Phase 2: exact-date session deletion -----------------------------------


def _seed_forget_surfaces(ctx, tmp_path):
    ctx.sessions_dir.mkdir(parents=True)
    (ctx.sessions_dir / "2026-08-13.jsonl").write_text(
        '{"ts":"2026-08-13 10:00","summary":"old"}\n', encoding="utf-8"
    )
    (ctx.sessions_dir / "2026-08-14.jsonl").write_text(
        '{"ts":"2026-08-14 10:00","summary":"keep"}\n', encoding="utf-8"
    )
    ctx.history_path.write_text(
        '{"ts":"2026-08-13 10:00","summary":"old"}\n'
        '{"ts":"2026-08-14 10:00","summary":"keep"}\n',
        encoding="utf-8",
    )
    ctx.path.write_text(
        "## Session 2026-08-13 10:00\n- Summary: old\n\n"
        "## Session 2026-08-14 10:00\n- Summary: keep\n",
        encoding="utf-8",
    )


def test_forget_date_preview_counts_without_mutation(tmp_path):
    ctx = _ctx(tmp_path)
    _seed_forget_surfaces(ctx, tmp_path)

    result = ctx.forget_date("2026-08-13", apply=False)

    assert result == {
        "date": "2026-08-13",
        "daily_entries": 1,
        "history_entries": 1,
        "rolling_sessions": 1,
        "deleted": False,
    }
    assert (ctx.sessions_dir / "2026-08-13.jsonl").exists()
    assert "2026-08-13" in ctx.history_path.read_text(encoding="utf-8")
    assert "2026-08-13" in ctx.path.read_text(encoding="utf-8")


def test_forget_date_apply_removes_only_selected_date(tmp_path):
    ctx = _ctx(tmp_path)
    _seed_forget_surfaces(ctx, tmp_path)

    result = ctx.forget_date("2026-08-13", apply=True)

    assert result["deleted"] is True
    assert not (ctx.sessions_dir / "2026-08-13.jsonl").exists()
    assert (ctx.sessions_dir / "2026-08-14.jsonl").exists()
    assert "2026-08-13" not in ctx.history_path.read_text(encoding="utf-8")
    assert "2026-08-14" in ctx.history_path.read_text(encoding="utf-8")
    assert "2026-08-13" not in ctx.path.read_text(encoding="utf-8")
    assert "2026-08-14" in ctx.path.read_text(encoding="utf-8")


def test_forget_date_rejects_non_iso_and_traversal(tmp_path):
    ctx = _ctx(tmp_path)

    for value in ("2026-8-1", "../2026-08-13", "2026-02-30", "all"):
        try:
            ctx.forget_date(value)
        except ValueError as exc:
            assert "YYYY-MM-DD" in str(exc)
        else:
            raise AssertionError(f"expected invalid date to fail: {value}")
