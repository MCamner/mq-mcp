import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import codegraph_lookup as cg


def _repo_with_graph(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    dbdir = repo / ".codegraph"
    dbdir.mkdir(parents=True)
    conn = sqlite3.connect(dbdir / "codegraph.db")
    conn.execute(
        "CREATE TABLE nodes (name TEXT, kind TEXT, file_path TEXT, start_line INTEGER, end_line INTEGER)"
    )
    conn.execute("CREATE TABLE edges (src_file TEXT, dst_file TEXT)")
    conn.execute("INSERT INTO nodes VALUES ('BridgetContext', 'class', 'mq-mcp/bridget_context.py', 36, 200)")
    conn.execute("INSERT INTO edges VALUES ('mq-mcp/bridge.py', 'mq-mcp/bridget_context.py')")
    conn.commit()
    conn.close()
    return repo


def test_symbol_lookup_reads_codegraph_db(tmp_path):
    repo = _repo_with_graph(tmp_path)

    rows = cg.symbol_lookup(repo, "Bridget")

    assert rows[0]["name"] == "BridgetContext"
    assert rows[0]["file"] == "mq-mcp/bridget_context.py"


def test_dependency_lookup_reads_edges(tmp_path):
    repo = _repo_with_graph(tmp_path)

    deps = cg.dependency_lookup(repo, "mq-mcp/bridge.py")

    assert deps["imports"] == ["mq-mcp/bridget_context.py"]


def test_hotspots_counts_edge_endpoints(tmp_path):
    repo = _repo_with_graph(tmp_path)

    rows = cg.hotspots(repo)

    assert rows[0]["edges"] == 1
