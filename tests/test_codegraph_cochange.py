"""Tests for CG-2.1 git co-change awareness (`bridget --co-change`).

Locks the CG-2.1 contract: co-change ranking derived purely from `git log`,
confidence-scored; best-effort read-only enrichment from the codegraph DB that
degrades to {} when absent; a formatter that never truncates paths; and a
synchronous dispatcher that needs no MCP/OpenAI. Boundary: read-only, no writes.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import codegraph_cochange as cc  # noqa: E402


# --- helpers ----------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(repo: Path, files: dict[str, str], msg: str) -> None:
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "Test")
    return repo


# --- co_change --------------------------------------------------------------


def test_co_change_ranks_and_scores(tmp_path):
    repo = _repo(tmp_path)
    # a.py always changes with b.py (3 commits); c.py only once with a.py.
    _commit(repo, {"a.py": "1", "b.py": "1"}, "c1")
    _commit(repo, {"a.py": "2", "b.py": "2"}, "c2")
    _commit(repo, {"a.py": "3", "b.py": "3", "c.py": "1"}, "c3")
    # an unrelated commit not touching a.py
    _commit(repo, {"d.py": "1"}, "c4")

    rows = cc.co_change(repo, "a.py", min_support=1)
    by_path = {r["path"]: r for r in rows}

    assert by_path["b.py"]["base"] == 3
    assert by_path["b.py"]["count"] == 3
    assert by_path["b.py"]["confidence"] == 1.0
    assert by_path["c.py"]["count"] == 1
    assert abs(by_path["c.py"]["confidence"] - 1 / 3) < 1e-9
    assert "d.py" not in by_path  # never co-changed with a.py
    # b.py (1.0) ranks above c.py (0.33)
    assert rows[0]["path"] == "b.py"


def test_co_change_min_support_filters_one_offs(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"a.py": "1", "b.py": "1"}, "c1")
    _commit(repo, {"a.py": "2", "b.py": "2"}, "c2")
    _commit(repo, {"a.py": "3", "c.py": "1"}, "c3")

    rows = cc.co_change(repo, "a.py", min_support=2)
    paths = {r["path"] for r in rows}
    assert "b.py" in paths  # 2 co-changes
    assert "c.py" not in paths  # only 1, below min_support


def test_co_change_unknown_target_empty(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"a.py": "1"}, "c1")
    assert cc.co_change(repo, "nope.py") == []


# --- _git_log_blocks --------------------------------------------------------


def test_git_log_blocks_parses_multifile_commits(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, {"a.py": "1", "b.py": "1"}, "c1")
    blocks = cc._git_log_blocks(repo, 10)
    assert len(blocks) == 1
    assert set(blocks[0]) == {"a.py", "b.py"}


def test_git_log_blocks_non_git_dir(tmp_path):
    assert cc._git_log_blocks(tmp_path, 10) == []


# --- enrich -----------------------------------------------------------------


def _graph_db(repo: Path, rows: list[tuple[str, str, str]]) -> None:
    """Build a minimal read-target codegraph DB: (file_path, kind, language)."""
    db_dir = repo / ".codegraph"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "codegraph.db")
    conn.execute(
        "CREATE TABLE nodes (file_path TEXT, kind TEXT, language TEXT)"
    )
    conn.executemany("INSERT INTO nodes VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()


def test_enrich_returns_symbol_counts(tmp_path):
    repo = _repo(tmp_path)
    _graph_db(
        repo,
        [
            ("a.py", "function", "python"),
            ("a.py", "class", "python"),
            ("b.py", "function", "python"),
        ],
    )
    out = cc.enrich(repo, ["a.py", "b.py", "missing.py"])
    assert out["a.py"]["symbols"] == 2
    assert out["a.py"]["in_graph"] is True
    assert "function" in out["a.py"]["kinds"]
    assert out["b.py"]["symbols"] == 1
    assert out["missing.py"]["in_graph"] is False


def test_enrich_absent_db_returns_empty(tmp_path):
    repo = _repo(tmp_path)  # no .codegraph
    assert cc.enrich(repo, ["a.py"]) == {}


# --- format_cochange --------------------------------------------------------


def test_format_includes_target_and_paths(tmp_path):
    rows = [{"path": "b.py", "count": 3, "base": 3, "confidence": 1.0}]
    out = cc.format_cochange("a.py", rows, window=200)
    assert "a.py" in out
    assert "b.py" in out
    assert "(3/3)" in out
    assert "200" in out


def test_format_empty_is_clear_message():
    out = cc.format_cochange("a.py", [])
    assert "No co-change history" in out
    assert "a.py" in out


def test_format_does_not_truncate_paths():
    # Regression for the bridget_runtime strip lesson: full path must survive.
    long = "mq-mcp/some/deeply/nested/module_name.py"
    rows = [
        {"path": long, "count": 2, "base": 4, "confidence": 0.5},
        {"path": "x.py", "count": 2, "base": 4, "confidence": 0.5},
    ]
    out = cc.format_cochange("a.py", rows)
    assert long in out


def test_format_includes_graph_enrichment():
    rows = [{"path": "b.py", "count": 2, "base": 2, "confidence": 1.0}]
    emap = {"b.py": {"symbols": 5, "kinds": "function,class", "in_graph": True}}
    out = cc.format_cochange("a.py", rows, emap)
    assert "[graph]" in out
    assert "5 symbols" in out


# --- dispatcher -------------------------------------------------------------


def test_maybe_handle_routes_co_change(tmp_path, capsys, monkeypatch):
    repo = _repo(tmp_path)
    _commit(repo, {"a.py": "1", "b.py": "1"}, "c1")
    _commit(repo, {"a.py": "2", "b.py": "2"}, "c2")
    monkeypatch.chdir(repo)

    assert cc.maybe_handle_cochange(["--co-change", "a.py"]) is True
    out = capsys.readouterr().out
    assert "b.py" in out


def test_maybe_handle_parses_window(tmp_path, monkeypatch):
    captured = {}

    def fake_handle(target, *, window, as_json=False):
        captured["target"] = target
        captured["window"] = window
        captured["as_json"] = as_json
        return 0

    monkeypatch.setattr(cc, "handle_cochange", fake_handle)
    assert cc.maybe_handle_cochange(["--co-change", "a.py", "--window", "50"]) is True
    assert captured == {"target": "a.py", "window": 50, "as_json": False}


def test_maybe_handle_ignores_unrelated_argv():
    assert cc.maybe_handle_cochange(["--history", "10"]) is False
    assert cc.maybe_handle_cochange(["just a prompt"]) is False


def test_maybe_handle_missing_target_prints_usage(capsys):
    assert cc.maybe_handle_cochange(["--co-change"]) is True
    assert "Usage" in capsys.readouterr().out


# --- evidence source: run_id + --json (CG-2.2) ------------------------------


def test_run_id_shape_is_stable_and_parseable():
    from datetime import datetime, timezone

    now = datetime(2026, 6, 29, 1, 2, 3, tzinfo=timezone.utc)
    rid = cc.run_id("/repos/mq-mcp", "mq-mcp/bridge.py", now=now)
    assert rid.startswith("cochange-run-20260629T010203Z-")
    # deterministic for the same (repo, target, time); distinct for a different target
    assert rid == cc.run_id("/repos/mq-mcp", "mq-mcp/bridge.py", now=now)
    assert rid != cc.run_id("/repos/mq-mcp", "mq-mcp/server.py", now=now)


def test_json_output_emits_run_id_and_rows(tmp_path, capsys, monkeypatch):
    import json as _json

    repo = _repo(tmp_path)
    _commit(repo, {"a.py": "1", "b.py": "1"}, "c1")
    _commit(repo, {"a.py": "2", "b.py": "2"}, "c2")
    monkeypatch.chdir(repo)

    assert cc.maybe_handle_cochange(["--co-change", "a.py", "--json"]) is True
    payload = _json.loads(capsys.readouterr().out)
    assert payload["run_id"].startswith("cochange-run-")
    assert payload["target"] == "a.py"
    assert payload["window"] == cc._DEFAULT_WINDOW
    assert "generated_at" in payload
    paths = {r["path"] for r in payload["rows"]}
    assert "b.py" in paths


def test_human_output_unchanged_without_json(tmp_path, capsys, monkeypatch):
    repo = _repo(tmp_path)
    _commit(repo, {"a.py": "1", "b.py": "1"}, "c1")
    _commit(repo, {"a.py": "2", "b.py": "2"}, "c2")
    monkeypatch.chdir(repo)

    cc.handle_cochange("a.py")
    out = capsys.readouterr().out
    assert "Files that change with" in out
    assert out.lstrip()[0] != "{"  # not JSON
