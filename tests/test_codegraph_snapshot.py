"""Tests for CG-2.2 graph snapshots + diff (`bridget --snapshot` / `--graph-diff`).

Locks the CG-2.2 contract: a snapshot captures graph totals + per-file symbol
counts and content hashes from the read-only codegraph DB, pinned to the current
git commit, and persists under $MQ_HOME; diff reports files added/removed/changed
between two snapshots; formatters never truncate paths; the dispatcher is
synchronous (no MCP/OpenAI). Boundary: read-only over the graph; the only write
is the snapshot's own JSON.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import codegraph_snapshot as cs  # noqa: E402


# --- helpers (mirror test_codegraph_cochange.py) ----------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-m", "seed")
    return repo


def _graph_db(repo: Path, files: list[tuple[str, str, str, int]], *, edges: int = 0) -> None:
    """Build a minimal codegraph DB: files=(path, content_hash, language, node_count)."""
    db_dir = repo / ".codegraph"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "codegraph.db")
    for t in ("files", "nodes", "edges"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.execute(
        "CREATE TABLE files (path TEXT, content_hash TEXT, language TEXT, node_count INTEGER)"
    )
    conn.execute("CREATE TABLE nodes (file_path TEXT, kind TEXT)")
    conn.execute("CREATE TABLE edges (source TEXT, target TEXT)")
    conn.executemany("INSERT INTO files VALUES (?, ?, ?, ?)", files)
    for path, _h, _l, n in files:
        conn.executemany(
            "INSERT INTO nodes VALUES (?, ?)", [(path, "function")] * int(n)
        )
    conn.executemany(
        "INSERT INTO edges VALUES (?, ?)", [("a", "b")] * int(edges)
    )
    conn.commit()
    conn.close()


def _use_mq_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MQ_HOME", str(tmp_path / "mqhome"))


# --- snapshot capture -------------------------------------------------------


def test_snapshot_writes_file_with_totals(tmp_path, monkeypatch):
    _use_mq_home(monkeypatch, tmp_path)
    repo = _repo(tmp_path)
    _graph_db(
        repo,
        [("a.py", "h1", "python", 3), ("b.py", "h2", "python", 1)],
        edges=4,
    )
    snap, path = cs.snapshot(repo)

    assert path.exists()
    assert snap["schema"] == "graph-snapshot.v1"
    assert snap["totals"] == {"nodes": 4, "edges": 4, "files": 2}
    assert snap["files"]["a.py"]["symbols"] == 3
    assert snap["files"]["a.py"]["content_hash"] == "h1"
    assert len(snap["commit"]) >= 7 and snap["commit"] != "unknown"
    # persisted JSON round-trips
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["files"]["b.py"]["symbols"] == 1


def test_snapshot_absent_db_is_valid_and_empty(tmp_path, monkeypatch):
    _use_mq_home(monkeypatch, tmp_path)
    repo = _repo(tmp_path)  # no .codegraph
    snap, path = cs.snapshot(repo)
    assert path.exists()
    assert snap["totals"] == {"nodes": 0, "edges": 0, "files": 0}
    assert snap["files"] == {}


# --- diff -------------------------------------------------------------------


def test_diff_detects_add_remove_change():
    a = {
        "commit": "aaaaaaaa",
        "totals": {"nodes": 5, "edges": 2, "files": 2},
        "files": {
            "keep.py": {"symbols": 2, "content_hash": "h1"},
            "gone.py": {"symbols": 1, "content_hash": "h2"},
        },
    }
    b = {
        "commit": "bbbbbbbb",
        "totals": {"nodes": 8, "edges": 3, "files": 2},
        "files": {
            "keep.py": {"symbols": 4, "content_hash": "h1b"},  # changed
            "new.py": {"symbols": 2, "content_hash": "h3"},  # added
        },
    }
    d = cs.diff(a, b)
    assert d["files_added"] == ["new.py"]
    assert d["files_removed"] == ["gone.py"]
    assert len(d["files_changed"]) == 1
    ch = d["files_changed"][0]
    assert ch["path"] == "keep.py"
    assert ch["symbols_from"] == 2 and ch["symbols_to"] == 4
    assert ch["hash_changed"] is True
    assert d["totals_delta"] == {"nodes": 3, "edges": 1, "files": 0}


def test_diff_no_changes_is_empty():
    a = {"totals": {"nodes": 1, "edges": 0, "files": 1}, "files": {"x.py": {"symbols": 1, "content_hash": "h"}}}
    d = cs.diff(a, a)
    assert d["files_added"] == []
    assert d["files_removed"] == []
    assert d["files_changed"] == []


# --- formatting -------------------------------------------------------------


def test_format_snapshot_includes_totals(tmp_path):
    snap = {
        "repo": "demo",
        "commit": "abcdef123456",
        "branch": "main",
        "totals": {"nodes": 10, "edges": 4, "files": 3},
    }
    out = cs.format_snapshot(snap, "/x/y.json")
    assert "demo" in out and "abcdef12" in out
    assert "nodes 10" in out and "files 3" in out


def test_format_diff_does_not_truncate_paths():
    long = "mq-mcp/some/deeply/nested/module_name.py"
    d = {
        "from": {"commit": "aaaaaaaa"},
        "to": {"commit": "bbbbbbbb"},
        "totals_delta": {"nodes": 1, "edges": 0, "files": 0},
        "files_added": [],
        "files_removed": [],
        "files_changed": [
            {"path": long, "symbols_from": 1, "symbols_to": 2, "hash_changed": True},
            {"path": "x.py", "symbols_from": 1, "symbols_to": 1, "hash_changed": True},
        ],
    }
    out = cs.format_diff(d)
    assert long in out
    assert "+1" in out  # signed totals delta


# --- handlers / dispatcher --------------------------------------------------


def test_handle_diff_needs_two_snapshots(tmp_path, monkeypatch, capsys):
    _use_mq_home(monkeypatch, tmp_path)
    repo = _repo(tmp_path)
    _graph_db(repo, [("a.py", "h1", "python", 1)])
    cs.snapshot(repo)  # only one
    rc = cs.handle_diff(str(repo))
    out = capsys.readouterr().out
    assert rc == 1
    assert "at least two snapshots" in out


def test_dispatcher_routes_snapshot_and_diff(tmp_path, monkeypatch, capsys):
    _use_mq_home(monkeypatch, tmp_path)
    repo = _repo(tmp_path)
    _graph_db(repo, [("a.py", "h1", "python", 2)], edges=1)
    monkeypatch.chdir(repo)

    assert cs.maybe_handle_snapshot(["--snapshot"]) is True
    assert "Captured graph snapshot" in capsys.readouterr().out

    # mutate the graph DB so the second snapshot differs, then diff
    _graph_db(repo, [("a.py", "h2", "python", 5), ("b.py", "h3", "python", 1)], edges=2)
    assert cs.maybe_handle_snapshot(["--snapshot"]) is True
    capsys.readouterr()
    assert cs.maybe_handle_snapshot(["--graph-diff"]) is True
    out = capsys.readouterr().out
    assert "Graph diff" in out
    assert "+ b.py" in out


def test_dispatcher_ignores_unrelated_argv():
    assert cs.maybe_handle_snapshot(["--co-change", "a.py"]) is False
    assert cs.maybe_handle_snapshot(["just a prompt"]) is False
