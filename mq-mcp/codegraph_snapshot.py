"""
codegraph_snapshot.py — Historical graph snapshots + diff for Bridget (CG-2.2).

Answers a question the static CodeGraph DB cannot: *how did the graph change
between two points in time*. CodeGraph (`.codegraph/codegraph.db`) holds only the
*current* structure — files / nodes / edges — with no history. CG-2.2 captures a
**snapshot** of that structure (totals + per-file symbol counts and content
hashes, pinned to the current git commit) and persists it under ``~/.mq/`` so two
snapshots can later be **diffed**: which files/symbols were added, removed, or
changed.

Boundary: like CG-2.1 co-change, this is **context only, not evidence, not a
producer**. It reads the graph read-only and reads git; the only thing it writes
is its own snapshot JSON (its single MQ-owned artifact). It emits no observation
and promotes no learning. Surfaced as synchronous CLI flags
``bridget --snapshot <repo>`` / ``bridget --graph-diff <repo>`` (no OpenAI client,
no MCP session), intercepted in bridge.py like --co-change / --workflow.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import codegraph_cochange as cc

SCHEMA = "graph-snapshot.v1"


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------


def _snapshot_root() -> Path:
    """Base dir for snapshots: ``$MQ_HOME/graph-snapshots`` (default ~/.mq).

    The ``MQ_HOME`` override keeps tests off the real home and matches
    ``bridget_context.CONTEXT_DIR = ~/.mq``.
    """
    base = os.environ.get("MQ_HOME")
    root = Path(base) if base else (Path.home() / ".mq")
    return root / "graph-snapshots"


def _slug(repo_path: str | Path) -> str:
    """Filesystem-safe per-repo directory key from the repo basename."""
    name = Path(repo_path).name or "repo"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "repo"


def _repo_dir(repo_path: str | Path) -> Path:
    return _snapshot_root() / _slug(repo_path)


# ----------------------------------------------------------------------
# Repo / arg resolution
# ----------------------------------------------------------------------


def _resolve_repo_arg(target: str | None) -> str | None:
    """Repo root for a snapshot/diff arg.

    ``target`` may be a registered repo name, a path, or None. Falls back to the
    pinned project, then the cwd git toplevel — the same precedence the co-change
    resolver uses.
    """
    if target:
        repos = cc.known_local_repos()
        if target in repos:
            return repos[target]
        return cc._resolve_repo(target)
    proj = cc.bridget_runtime.get_project()
    if proj and proj.get("path"):
        return proj["path"]
    return cc._git_line(Path.cwd(), ["rev-parse", "--show-toplevel"])


# ----------------------------------------------------------------------
# Snapshot capture (read-only over the graph; reads git HEAD)
# ----------------------------------------------------------------------


def _read_graph(repo_path: str | Path) -> tuple[dict, dict]:
    """Return (totals, files) from the repo's codegraph DB, read-only.

    ``totals`` = {nodes, edges, files}; ``files`` maps repo-relative path ->
    {symbols, content_hash, language}. Best-effort: missing/unreadable DB yields
    zeroed totals and an empty files map (never raises).
    """
    totals = {"nodes": 0, "edges": 0, "files": 0}
    files: dict[str, dict] = {}
    db = Path(repo_path) / ".codegraph" / "codegraph.db"
    if not db.exists():
        return totals, files
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return totals, files
    try:
        cur = conn.cursor()
        for key, table in (("nodes", "nodes"), ("edges", "edges"), ("files", "files")):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 (fixed names)
                row = cur.fetchone()
                totals[key] = int(row[0]) if row and row[0] is not None else 0
            except sqlite3.Error:
                totals[key] = 0
        try:
            cur.execute("SELECT path, content_hash, language, node_count FROM files")
            for path, content_hash, language, node_count in cur.fetchall():
                files[cc._norm(path)] = {
                    "symbols": int(node_count or 0),
                    "content_hash": content_hash or "",
                    "language": language or "",
                }
        except sqlite3.Error:
            files = {}
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass
    return totals, files


def snapshot(repo_path: str | Path) -> tuple[dict, Path]:
    """Capture a ``graph-snapshot.v1`` for ``repo_path`` and persist it.

    Returns (snapshot_dict, written_path). The snapshot pins the current graph
    structure to the current git commit/branch.
    """
    commit = cc._git_line(repo_path, ["rev-parse", "HEAD"]) or "unknown"
    branch = cc._git_line(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    totals, files = _read_graph(repo_path)
    now = datetime.now(timezone.utc)
    snap = {
        "schema": SCHEMA,
        "repo": _slug(repo_path),
        "commit": commit,
        "branch": branch,
        "timestamp": now.isoformat(),
        "totals": totals,
        "files": files,
    }
    short = commit[:8] if commit != "unknown" else "nogit"
    # Microseconds keep two snapshots at the same commit/second distinct while
    # remaining lexically (= chronologically) sortable for load_snapshots().
    stamp = now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond:06d}Z"
    out_dir = _repo_dir(repo_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stamp}-{short}.json"
    path.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
    return snap, path


# ----------------------------------------------------------------------
# Snapshot loading + diff
# ----------------------------------------------------------------------


def load_snapshots(repo_path: str | Path) -> list[Path]:
    """Snapshot files for a repo, oldest first (lexical = chronological)."""
    d = _repo_dir(repo_path)
    if not d.exists():
        return []
    return sorted(d.glob("*.json"))


def _read_snapshot(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def diff(a: dict, b: dict) -> dict:
    """Diff two snapshot dicts (a = older, b = newer).

    A file is *changed* when its content hash or symbol count differs.
    """
    fa: dict[str, dict] = a.get("files", {})
    fb: dict[str, dict] = b.get("files", {})
    added = sorted(p for p in fb if p not in fa)
    removed = sorted(p for p in fa if p not in fb)
    changed = []
    for p in sorted(set(fa) & set(fb)):
        x, y = fa[p], fb[p]
        hash_changed = x.get("content_hash") != y.get("content_hash")
        sym_changed = x.get("symbols") != y.get("symbols")
        if hash_changed or sym_changed:
            changed.append(
                {
                    "path": p,
                    "symbols_from": x.get("symbols", 0),
                    "symbols_to": y.get("symbols", 0),
                    "hash_changed": hash_changed,
                }
            )
    ta, tb = a.get("totals", {}), b.get("totals", {})
    totals_delta = {
        k: int(tb.get(k, 0)) - int(ta.get(k, 0)) for k in ("nodes", "edges", "files")
    }
    return {
        "from": {"commit": a.get("commit"), "timestamp": a.get("timestamp")},
        "to": {"commit": b.get("commit"), "timestamp": b.get("timestamp")},
        "totals_delta": totals_delta,
        "files_added": added,
        "files_removed": removed,
        "files_changed": changed,
    }


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------


def format_snapshot(snap: dict, path: str | Path) -> str:
    t = snap.get("totals", {})
    return (
        f"Captured graph snapshot for {snap.get('repo')} "
        f"@ {(snap.get('commit') or '')[:8]} ({snap.get('branch')})\n"
        f"  nodes {t.get('nodes', 0)}  edges {t.get('edges', 0)}  "
        f"files {t.get('files', 0)}\n"
        f"  -> {path}"
    )


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def format_diff(d: dict) -> str:
    af = d.get("from", {})
    bf = d.get("to", {})
    td = d.get("totals_delta", {})
    lines = [
        f"Graph diff {(af.get('commit') or '')[:8]} -> {(bf.get('commit') or '')[:8]}:",
        f"  totals  nodes {_signed(td.get('nodes', 0))}  "
        f"edges {_signed(td.get('edges', 0))}  files {_signed(td.get('files', 0))}",
    ]
    added = d.get("files_added", [])
    removed = d.get("files_removed", [])
    changed = d.get("files_changed", [])
    if not (added or removed or changed):
        lines.append("  no file-level changes between these snapshots.")
        return "\n".join(lines)
    for p in added:
        lines.append(f"  + {p}")
    for p in removed:
        lines.append(f"  - {p}")
    if changed:
        width = max(len(c["path"]) for c in changed)
        for c in changed:
            # ljust on the full path — never slice, so paths are not truncated.
            delta = f"{c['symbols_from']}->{c['symbols_to']} symbols"
            mark = " hash" if c["hash_changed"] else ""
            lines.append(f"  ~ {c['path'].ljust(width)}  {delta}{mark}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Command handlers / dispatcher (synchronous; print and return)
# ----------------------------------------------------------------------


def handle_snapshot(target: str | None = None) -> int:
    repo_path = _resolve_repo_arg(target)
    if not repo_path:
        print("Not inside a git repo and no project pinned.")
        return 1
    snap, path = snapshot(repo_path)
    print(format_snapshot(snap, path))
    return 0


def _match_snapshot(snaps: list[Path], ident: str) -> Path | None:
    for s in snaps:
        if s.stem == ident or s.stem.startswith(ident) or ident in s.name:
            return s
    return None


def handle_diff(
    target: str | None = None, *, frm: str | None = None, to: str | None = None
) -> int:
    repo_path = _resolve_repo_arg(target)
    if not repo_path:
        print("Not inside a git repo and no project pinned.")
        return 1
    snaps = load_snapshots(repo_path)
    if len(snaps) < 2:
        have = f" (have {len(snaps)})" if snaps else ""
        print(
            f"Need at least two snapshots to diff{have}; "
            f"run `bridget --snapshot {_slug(repo_path)}` first."
        )
        for s in snaps:
            print(f"  {s.stem}")
        return 1
    a = _match_snapshot(snaps, frm) if frm else snaps[-2]
    b = _match_snapshot(snaps, to) if to else snaps[-1]
    if a is None or b is None:
        print("Could not resolve the requested snapshot id(s).")
        for s in snaps:
            print(f"  {s.stem}")
        return 1
    print(format_diff(diff(_read_snapshot(a), _read_snapshot(b))))
    return 0


def _arg_after(argv: list[str], flag: str) -> str | None:
    """Positional value immediately after ``flag`` if it is not another flag."""
    i = argv.index(flag)
    if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
        return argv[i + 1]
    return None


def _opt(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        j = argv.index(flag)
        if j + 1 < len(argv) and not argv[j + 1].startswith("-"):
            return argv[j + 1]
    return None


def maybe_handle_snapshot(argv: list[str]) -> bool:
    """Handle ``--snapshot`` / ``--graph-diff`` synchronously as a pre-flight.

    Returns True if handled (caller should exit), so the flag never reaches the
    async bridge or the OpenAI/MCP path.
    """
    if "--snapshot" in argv:
        handle_snapshot(_arg_after(argv, "--snapshot"))
        return True
    if "--graph-diff" in argv:
        handle_diff(
            _arg_after(argv, "--graph-diff"),
            frm=_opt(argv, "--from"),
            to=_opt(argv, "--to"),
        )
        return True
    return False
