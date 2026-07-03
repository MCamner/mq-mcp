"""Tests for Bridget Runtime (BR-1): --project / --history / --continue.

Locks the BR-1 contract: an append-only history log distinct from the bounded
rolling store; a persistent project pin resolved via the repo registry; a
read-only git/review brief; and synchronous handlers that need no MCP/OpenAI.
Honors the memory boundary — these only read and pin context, never promote.
"""

import functools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import bridget_runtime as br  # noqa: E402
from bridget_context import BridgetContext  # noqa: E402


# --- history store: record() + read_history() -------------------------------


def _ctx(tmp_path: Path) -> BridgetContext:
    return BridgetContext(
        path=tmp_path / "bridget-context.md",
        history_path=tmp_path / "bridget-history.jsonl",
        max_sessions=5,
    )


def test_record_appends_history_line_with_project_and_branch(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.record("do x", ["git_status"], "did x", project="mq-mcp", branch="main")

    lines = (tmp_path / "bridget-history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["project"] == "mq-mcp"
    assert entry["branch"] == "main"
    assert entry["tools"] == ["git_status"]
    assert entry["summary"] == "did x"
    assert "ts" in entry


def test_read_history_newest_first_and_limit(tmp_path):
    ctx = _ctx(tmp_path)
    for i in range(4):
        ctx.record(f"p{i}", [], f"a{i}", project="mq-mcp")

    recent = ctx.read_history(limit=2)
    assert [e["summary"] for e in recent] == ["a3", "a2"]
    assert len(ctx.read_history(limit=20)) == 4


def test_history_is_full_depth_while_markdown_rotates_to_five(tmp_path):
    ctx = _ctx(tmp_path)
    for i in range(7):
        ctx.record(f"p{i}", [], f"a{i}")

    # Rolling markdown store stays bounded ...
    md = (tmp_path / "bridget-context.md").read_text(encoding="utf-8")
    assert md.count("## Session ") == 5
    # ... but the jsonl history keeps everything.
    assert len(ctx.read_history(limit=100)) == 7


def test_record_history_is_best_effort_no_raise(tmp_path):
    # history_path under a regular file -> mkdir/open raises OSError internally.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    ctx = BridgetContext(
        path=tmp_path / "bridget-context.md",
        history_path=blocker / "nested" / "history.jsonl",
    )
    ctx.record("p", [], "a")  # must not raise
    assert ctx.read_history() == []


# --- project pin ------------------------------------------------------------


def test_project_pin_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "PROJECT_FILE", tmp_path / "bridget-project")
    assert br.get_project() is None

    entry = br.set_project("mq-mcp")  # always present in the registry
    assert entry is not None
    assert entry["name"] == "mq-mcp"
    assert br.get_project()["name"] == "mq-mcp"

    br.clear_project()
    assert br.get_project() is None


def test_set_project_unknown_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "PROJECT_FILE", tmp_path / "bridget-project")
    assert br.set_project("definitely-not-a-repo") is None


# --- git brief + last review ------------------------------------------------


def _git_repo(path: Path) -> Path:
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", *a], cwd=str(path), capture_output=True, text=True
    )
    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    (path / "f.txt").write_text("hello", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-qm", "init")
    return path


def test_repo_brief_reports_branch_and_clean(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    brief = br.repo_brief(repo)
    assert "branch:" in brief
    assert "clean" in brief


def test_repo_brief_reports_dirty(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    (repo / "new.txt").write_text("x", encoding="utf-8")
    brief = br.repo_brief(repo)
    assert "dirty: 1 file" in brief
    assert "new.txt" in brief


def test_repo_brief_dirty_filename_not_truncated(tmp_path):
    # A modified (tracked) file yields a " M <path>" porcelain line whose leading
    # space _git() strips — the filename must still be intact, not "f.txt"->".txt".
    repo = _git_repo(tmp_path / "repo")
    (repo / "f.txt").write_text("changed", encoding="utf-8")
    brief = br.repo_brief(repo)
    assert "f.txt" in brief
    assert ".txt," not in brief  # no leading-char loss


def test_repo_brief_non_git_is_graceful(tmp_path):
    assert "not a git repo" in br.repo_brief(tmp_path)


def test_last_review_picks_newest(tmp_path):
    hist = tmp_path / "review_engine" / "memory"
    hist.mkdir(parents=True)
    (hist / "review_history.json").write_text(
        json.dumps(
            {
                "a.py": [{"file_path": "a.py", "timestamp": 1, "timestamp_iso": "T1", "finding_count": 2}],
                "b.py": [{"file_path": "b.py", "timestamp": 9, "timestamp_iso": "T9", "finding_count": 5}],
            }
        ),
        encoding="utf-8",
    )
    out = br.last_review(tmp_path)
    assert out is not None
    assert "b.py" in out and "T9" in out


def test_last_review_absent_returns_none(tmp_path):
    assert br.last_review(tmp_path) is None


# --- synchronous handlers (no MCP/OpenAI) -----------------------------------


def test_handle_history_prints_entries(tmp_path, monkeypatch, capsys):
    jsonl = tmp_path / "bridget-history.jsonl"
    ctx = BridgetContext(path=tmp_path / "ctx.md", history_path=jsonl)
    ctx.record("p", ["git_status"], "summary text", project="mq-mcp")

    monkeypatch.setattr(
        br, "BridgetContext", functools.partial(BridgetContext, history_path=jsonl)
    )
    br.handle_history(limit=10)
    out = capsys.readouterr().out
    assert "[mq-mcp]" in out
    assert "summary text" in out
    assert "git_status" in out


def test_handle_history_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        br,
        "BridgetContext",
        functools.partial(BridgetContext, history_path=tmp_path / "none.jsonl"),
    )
    br.handle_history()
    assert "No session history" in capsys.readouterr().out


def test_handle_project_set_show_and_unknown(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(br, "PROJECT_FILE", tmp_path / "bridget-project")

    br.handle_project("mq-mcp")
    assert "Pinned project: mq-mcp" in capsys.readouterr().out

    br.handle_project(None)
    assert "Pinned project: mq-mcp" in capsys.readouterr().out

    br.handle_project("nope-repo")
    assert "Unknown repo" in capsys.readouterr().out


def test_handle_continue_without_pin(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(br, "PROJECT_FILE", tmp_path / "bridget-project")
    # Isolate the session read to an empty log so no real ~/.mq history leaks in.
    monkeypatch.setattr(
        br,
        "BridgetContext",
        functools.partial(BridgetContext, history_path=tmp_path / "none.jsonl"),
    )
    br.handle_continue()
    assert "No project pinned" in capsys.readouterr().out


# --- Phase 4: REPL session tagging + --continue resume ----------------------


def test_session_kind_repl_and_oneshot():
    assert br._session_kind({"chat_mode": True, "turns": 3}) == " (REPL, 3 turns)"
    assert br._session_kind({"chat_mode": True}) == " (REPL)"
    assert br._session_kind({}) == ""
    assert br._session_kind({"turns": 5}) == ""  # turns without chat_mode: one-shot


def test_last_session_prefers_repl_then_newest():
    entries = [
        {"ts": "t3", "summary": "newest one-shot"},
        {"ts": "t2", "chat_mode": True, "summary": "repl"},
        {"ts": "t1", "summary": "old"},
    ]
    assert br._last_session(entries)["summary"] == "repl"
    assert br._last_session([{"summary": "only"}])["summary"] == "only"
    assert br._last_session([]) is None


def test_handle_history_tags_repl_turn_count(tmp_path, monkeypatch, capsys):
    jsonl = tmp_path / "bridget-history.jsonl"
    ctx = BridgetContext(path=tmp_path / "ctx.md", history_path=jsonl)
    ctx.record(
        "p", ["git_status"], "s", project="mq-mcp",
        turns=5, duration_s=3.0, do_mode=False, chat_mode=True,
    )
    monkeypatch.setattr(
        br, "BridgetContext", functools.partial(BridgetContext, history_path=jsonl)
    )
    br.handle_history(limit=10)
    assert "(REPL, 5 turns)" in capsys.readouterr().out


def test_handle_continue_resumes_last_repl_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(br, "PROJECT_FILE", tmp_path / "bridget-project")  # no pin
    jsonl = tmp_path / "bridget-history.jsonl"
    ctx = BridgetContext(path=tmp_path / "ctx.md", history_path=jsonl)
    ctx.record(
        "resume this", ["git_status"], "did the thing",
        turns=2, chat_mode=True,
    )
    monkeypatch.setattr(
        br, "BridgetContext", functools.partial(BridgetContext, history_path=jsonl)
    )
    br.handle_continue()
    out = capsys.readouterr().out
    assert "Last session" in out
    assert "(REPL, 2 turns)" in out
    assert "resume this" in out
    assert "did the thing" in out
    # Still reports the missing pin after the resume summary.
    assert "No project pinned" in out


# --- pre-flight dispatcher --------------------------------------------------


def test_maybe_handle_runtime_command_routes(monkeypatch):
    calls = {}
    monkeypatch.setattr(br, "handle_history", lambda limit=20: calls.update(history=limit))
    monkeypatch.setattr(br, "handle_continue", lambda: calls.update(cont=True))
    monkeypatch.setattr(br, "handle_project", lambda name: calls.update(project=name))

    assert br.maybe_handle_runtime_command(["--history", "5"]) is True
    assert calls["history"] == 5
    assert br.maybe_handle_runtime_command(["--continue"]) is True
    assert calls["cont"] is True
    assert br.maybe_handle_runtime_command(["--project", "mq-mcp"]) is True
    assert calls["project"] == "mq-mcp"
    assert br.maybe_handle_runtime_command(["--project"]) is True
    assert calls["project"] is None
    assert br.maybe_handle_runtime_command(["hello world"]) is False
