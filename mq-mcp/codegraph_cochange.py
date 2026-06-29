"""
codegraph_cochange.py — Git co-change awareness for Bridget (CG-2.1).

Answers a question the static CodeGraph DB cannot: *which files historically
change together with file X*. CodeGraph (`.codegraph/codegraph.db`) is purely
structural — files / nodes / edges, no git history — so the temporal co-change
dimension is derived here from `git log`, then optionally enriched read-only
from the graph for symbol context.

Boundary: Bridget/CG-2 is **not a memory producer** — it is an **evidence
source**. It reads git and reads the graph; it writes nothing, emits no
observation, and promotes no learning. mq-agent is the producer that may wrap a
co-change result as a `memory-observation.v1` record (`producer: mq-agent`,
`evidence:[{source:"bridget/cg-2", reference:<run_id>}]`); mqobsidian alone
scores, promotes, and audits. To serve as a clean evidence source this module
exposes a stable `run_id` and a machine-readable `--json` output for mq-agent to
reference. Surfaced as the synchronous CLI flag `bridget --co-change <file>`
(no OpenAI client, no MCP session), intercepted in bridge.py like --workflow /
--history.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import bridget_runtime

_GIT_TIMEOUT = 10
_DEFAULT_WINDOW = 300
_DEFAULT_MIN_SUPPORT = 2

# Unit-separator delimiter for `git log --format=%x1f%H`; will not appear in
# commit hashes or file paths, so it is a safe block boundary.
_SEP = "\x1f"


def known_local_repos() -> dict[str, str]:
    """Read repo registry from MQ_MCP_LOCAL_REPOS (same logic as bridge.py)."""
    # Reuse the runtime resolver so the registry stays defined in one place.
    return bridget_runtime.known_local_repos()


# ----------------------------------------------------------------------
# Git plumbing
# ----------------------------------------------------------------------


def _git_raw(cwd: str | Path, args: list[str]) -> str | None:
    """Run git, returning raw stdout (no strip) or None on any failure.

    Unlike bridget_runtime._git this does NOT strip, so the first file line of a
    porcelain/name-only block keeps its content intact.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _git_line(cwd: str | Path, args: list[str]) -> str | None:
    """Run git, returning a single stripped line (e.g. rev-parse output)."""
    out = _git_raw(cwd, args)
    return out.strip() if out else None


def _norm(path: str) -> str:
    """Normalize a path to the repo-relative, forward-slash form git emits."""
    p = path.replace("\\", "/").strip()
    return p[2:] if p.startswith("./") else p


def run_id(repo: str | Path, target: str, *, now: datetime | None = None) -> str:
    """Stable id for a co-change run, referenced by mq-agent as evidence.

    Form ``cochange-run-<YYYYMMDDTHHMMSSZ>-<8hex>`` where the hex is a digest of
    (repo, target) so the same query at the same second is reproducible and two
    different queries never collide.
    """
    now = now or datetime.now(timezone.utc)
    digest = hashlib.sha1(f"{repo}\x1f{target}".encode()).hexdigest()[:8]
    return f"cochange-run-{now.strftime('%Y%m%dT%H%M%SZ')}-{digest}"


# ----------------------------------------------------------------------
# Co-change core (pure, git-derived)
# ----------------------------------------------------------------------


def _git_log_blocks(repo_path: str | Path, window: int) -> list[list[str]]:
    """Return one file-list per commit over the last ``window`` commits.

    Single `git log` pass: ``--format=%x1f%H --name-only`` prefixes each commit
    with a SEP+hash line, so splitting stdout on SEP yields per-commit blocks.
    Tolerates empty output and a non-git directory (returns []).
    """
    out = _git_raw(
        repo_path,
        ["log", "-n", str(window), "--no-merges", "--format=%x1f%H", "--name-only"],
    )
    if not out:
        return []
    blocks: list[list[str]] = []
    for chunk in out.split(_SEP):
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        # lines[0] is the commit hash; the rest are changed file paths.
        files = [ln for ln in lines[1:] if ln.strip()]
        if files:
            blocks.append(files)
    return blocks


def co_change(
    repo_path: str | Path,
    target: str,
    *,
    window: int = _DEFAULT_WINDOW,
    min_support: int = _DEFAULT_MIN_SUPPORT,
) -> list[dict]:
    """Files that co-change with ``target`` over the last ``window`` commits.

    Returns rows ``{path, count, base, confidence}`` where ``base`` is the number
    of commits touching the target, ``count`` the number of those that also
    touched the row's file, and ``confidence = count / base``. Filtered by
    ``min_support`` and sorted by (confidence, count) desc. Empty list when the
    target has no history in the window.
    """
    target = _norm(target)
    base = 0
    counts: dict[str, int] = {}
    for files in _git_log_blocks(repo_path, window):
        fileset = {_norm(f) for f in files}
        if target not in fileset:
            continue
        base += 1
        for f in fileset:
            if f != target:
                counts[f] = counts.get(f, 0) + 1
    if base == 0:
        return []
    rows = [
        {"path": f, "count": c, "base": base, "confidence": c / base}
        for f, c in counts.items()
        if c >= min_support
    ]
    rows.sort(key=lambda r: (-float(r["confidence"]), -int(r["count"]), str(r["path"])))
    return rows


# ----------------------------------------------------------------------
# Read-only graph enrichment
# ----------------------------------------------------------------------


def enrich(repo_path: str | Path, paths: list[str]) -> dict[str, dict]:
    """Read-only symbol context for ``paths`` from the repo's codegraph DB.

    Best-effort and strictly read: opens ``.codegraph/codegraph.db`` with a
    ``mode=ro`` URI, never writes, and degrades to ``{}`` when the DB is absent
    or unreadable. A path not present in the graph gets ``in_graph: False``.
    """
    db = Path(repo_path) / ".codegraph" / "codegraph.db"
    if not db.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    out: dict[str, dict] = {}
    try:
        cur = conn.cursor()
        for p in paths:
            try:
                cur.execute(
                    "SELECT COUNT(*), GROUP_CONCAT(DISTINCT kind), MAX(language) "
                    "FROM nodes WHERE file_path = ?",
                    (p,),
                )
                row = cur.fetchone()
            except sqlite3.Error:
                continue
            n = (row[0] if row else 0) or 0
            out[p] = {
                "symbols": n,
                "kinds": (row[1] or "") if row else "",
                "language": (row[2] or "") if row else "",
                "in_graph": bool(n),
            }
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass
    return out


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------


# Generic graph kinds that say little about what a file *is*; prefer a more
# descriptive kind (class/function/...) when one is present.
_GENERIC_KINDS = ("file", "import", "variable")


def _primary_kind(kinds: str | None) -> str:
    parts = [k for k in (kinds or "").split(",") if k]
    if not parts:
        return "?"
    for k in parts:
        if k not in _GENERIC_KINDS:
            return k
    return parts[0]


def format_cochange(
    target: str,
    rows: list[dict],
    enrich_map: dict[str, dict] | None = None,
    *,
    window: int | None = None,
) -> str:
    """Human-readable co-change block; clear message when there is no history."""
    if not rows:
        return f"No co-change history found for {target}."
    enrich_map = enrich_map or {}
    suffix = f" (last {window} commits)" if window else ""
    width = max(len(r["path"]) for r in rows)
    lines = [f"Files that change with {target}{suffix}:"]
    for r in rows:
        conf = f"{r['confidence']:.2f}"
        meta = f"({r['count']}/{r['base']})"
        # ljust on the full path — never slice, so paths are not truncated.
        line = f"  {r['path'].ljust(width)}  {conf}  {meta}"
        e = enrich_map.get(r["path"])
        if e and e.get("in_graph"):
            line += f"  [graph] {_primary_kind(e.get('kinds'))} · {e['symbols']} symbols"
        lines.append(line)
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Repo / target resolution
# ----------------------------------------------------------------------


def _resolve_repo(target: str) -> str | None:
    """Repo root for ``target``: its git toplevel, else pinned project, else cwd."""
    p = Path(target)
    for cand in (p, Path.cwd() / p):
        if cand.exists():
            anchor = cand.parent if cand.is_file() else cand
            top = _git_line(anchor, ["rev-parse", "--show-toplevel"])
            if top:
                return top
    proj = bridget_runtime.get_project()
    if proj and proj.get("path"):
        return proj["path"]
    return _git_line(Path.cwd(), ["rev-parse", "--show-toplevel"])


def _rel_to_repo(repo_path: str | Path, target: str) -> str:
    """Repo-relative form of ``target``; assume already relative if outside repo."""
    p = Path(target)
    abs_p = p if p.is_absolute() else (Path.cwd() / p)
    if abs_p.exists():
        try:
            return _norm(str(abs_p.resolve().relative_to(Path(repo_path).resolve())))
        except ValueError:
            pass
    return _norm(target)


# ----------------------------------------------------------------------
# Command handler / dispatcher (synchronous; print and return)
# ----------------------------------------------------------------------


def handle_cochange(
    target: str, *, window: int = _DEFAULT_WINDOW, as_json: bool = False
) -> int:
    repo_path = _resolve_repo(target)
    if not repo_path:
        print("Not inside a git repo and no project pinned.")
        return 1
    rel = _rel_to_repo(repo_path, target)
    rows = co_change(repo_path, rel, window=window)
    if as_json:
        # Machine-readable evidence-source output for mq-agent (the producer).
        # No enrichment, no side effects — just the derived rows + a stable id.
        now = datetime.now(timezone.utc)
        payload = {
            "run_id": run_id(repo_path, rel, now=now),
            "repo": Path(repo_path).name,
            "target": rel,
            "window": window,
            "generated_at": now.isoformat(),
            "rows": rows,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    emap = enrich(repo_path, [rel, *[r["path"] for r in rows]])
    print(format_cochange(rel, rows, emap, window=window))
    return 0


def maybe_handle_cochange(argv: list[str]) -> bool:
    """Handle ``--co-change <file> [--window N]`` synchronously as a pre-flight.

    Returns True if handled (caller should exit), so the flag never reaches the
    async bridge or the OpenAI/MCP path.
    """
    if "--co-change" not in argv:
        return False
    i = argv.index("--co-change")
    target = None
    if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
        target = argv[i + 1]
    window = _DEFAULT_WINDOW
    if "--window" in argv:
        j = argv.index("--window")
        if j + 1 < len(argv) and argv[j + 1].isdigit():
            window = int(argv[j + 1])
    if not target:
        print("Usage: bridget --co-change <file> [--window N] [--json]")
        return True
    handle_cochange(target, window=window, as_json="--json" in argv)
    return True
