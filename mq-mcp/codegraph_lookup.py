"""
codegraph_lookup.py — Read-only CodeGraph lookup commands for Bridget.

Boundary: CodeGraph is context only. These commands read the local
``.codegraph/codegraph.db`` and print operator context; they do not emit memory
observations, score evidence, write learning, or orchestrate work.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import codegraph_cochange as cc


def _resolve_repo_arg(target: str | None) -> str | None:
    if target:
        repos = cc.known_local_repos()
        if target in repos:
            return repos[target]
        return cc._resolve_repo(target)
    proj = cc.bridget_runtime.get_project()
    if proj and proj.get("path"):
        return proj["path"]
    return cc._git_line(Path.cwd(), ["rev-parse", "--show-toplevel"])


def _connect(repo_path: str | Path) -> sqlite3.Connection | None:
    db = Path(repo_path) / ".codegraph" / "codegraph.db"
    if not db.exists():
        return None
    try:
        return sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def symbol_lookup(repo_path: str | Path, query: str, *, limit: int = 20) -> list[dict]:
    conn = _connect(repo_path)
    if conn is None:
        return []
    like = f"%{query}%"
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name, kind, file_path, start_line, end_line
            FROM nodes
            WHERE name LIKE ?
            ORDER BY file_path, start_line
            LIMIT ?
            """,
            (like, limit),
        )
        return [
            {
                "name": row[0],
                "kind": row[1],
                "file": row[2],
                "start": row[3],
                "end": row[4],
            }
            for row in cur.fetchall()
        ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def dependency_lookup(repo_path: str | Path, path: str, *, limit: int = 30) -> dict:
    conn = _connect(repo_path)
    if conn is None:
        return {"imports": [], "imported_by": []}
    norm = cc._norm(path)
    try:
        cur = conn.cursor()
        imports: list[str] = []
        imported_by: list[str] = []
        for sql, bucket, param_index in (
            (
                "SELECT DISTINCT dst_file FROM edges WHERE src_file = ? AND dst_file IS NOT NULL ORDER BY dst_file LIMIT ?",
                imports,
                norm,
            ),
            (
                "SELECT DISTINCT src_file FROM edges WHERE dst_file = ? AND src_file IS NOT NULL ORDER BY src_file LIMIT ?",
                imported_by,
                norm,
            ),
        ):
            try:
                cur.execute(sql, (param_index, limit))
                bucket.extend(str(row[0]) for row in cur.fetchall() if row and row[0])
            except sqlite3.Error:
                continue
        return {"imports": imports, "imported_by": imported_by}
    finally:
        conn.close()


def hotspots(repo_path: str | Path, *, limit: int = 15) -> list[dict]:
    conn = _connect(repo_path)
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT file_path, COUNT(*) AS edges
            FROM (
              SELECT src_file AS file_path FROM edges WHERE src_file IS NOT NULL
              UNION ALL
              SELECT dst_file AS file_path FROM edges WHERE dst_file IS NOT NULL
            )
            GROUP BY file_path
            ORDER BY edges DESC, file_path
            LIMIT ?
            """,
            (limit,),
        )
        return [{"file": row[0], "edges": int(row[1] or 0)} for row in cur.fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def handle_symbol(query: str | None, target: str | None = None) -> int:
    if not query:
        print("Usage: bridget --symbol <name> [repo]")
        return 1
    repo_path = _resolve_repo_arg(target)
    if not repo_path:
        print("Not inside a git repo and no project pinned.")
        return 1
    rows = symbol_lookup(repo_path, query)
    if not rows:
        print(f"No CodeGraph symbols matched: {query}")
        return 0
    print(f"CodeGraph symbols matching {query!r}:")
    for row in rows:
        loc = f"{row['file']}:{row['start']}" if row.get("start") else row["file"]
        print(f"  {row['kind'] or '?'} {row['name']} — {loc}")
    return 0


def handle_dependencies(path: str | None, target: str | None = None) -> int:
    if not path:
        print("Usage: bridget --dependencies <file> [repo]")
        return 1
    repo_path = _resolve_repo_arg(target)
    if not repo_path:
        print("Not inside a git repo and no project pinned.")
        return 1
    deps = dependency_lookup(repo_path, path)
    print(f"CodeGraph dependencies for {cc._norm(path)}:")
    print("  imports:")
    for item in deps["imports"] or ["-"]:
        print(f"    {item}")
    print("  imported by:")
    for item in deps["imported_by"] or ["-"]:
        print(f"    {item}")
    return 0


def handle_hotspots(target: str | None = None) -> int:
    repo_path = _resolve_repo_arg(target)
    if not repo_path:
        print("Not inside a git repo and no project pinned.")
        return 1
    rows = hotspots(repo_path)
    if not rows:
        print("No CodeGraph hotspot data available.")
        return 0
    print("CodeGraph hotspots:")
    for row in rows:
        print(f"  {row['edges']:>4}  {row['file']}")
    return 0


def _arg_after(argv: list[str], flag: str) -> str | None:
    i = argv.index(flag)
    if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
        return argv[i + 1]
    return None


def maybe_handle_lookup(argv: list[str]) -> bool:
    if "--symbol" in argv:
        handle_symbol(_arg_after(argv, "--symbol"))
        return True
    if "--dependencies" in argv:
        handle_dependencies(_arg_after(argv, "--dependencies"))
        return True
    if "--hotspots" in argv:
        handle_hotspots(_arg_after(argv, "--hotspots"))
        return True
    return False
