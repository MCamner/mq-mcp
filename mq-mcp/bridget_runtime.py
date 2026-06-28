"""
bridget_runtime.py — Bridget Runtime helpers for --project / --history / --continue.

Self-contained: pure helpers plus synchronous command handlers that print and
return. No OpenAI client and no MCP session are needed, so bridge.py intercepts
these flags before the async bridge starts (same pattern as --workflow).

Boundary: this only *reads and pins context* (project, git state, prior sessions,
last review). It never writes learning or promotes anything — sessions are
context, not evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from bridget_context import CONTEXT_DIR, BridgetContext

# Persistent "current project" pin, sibling to the session stores in ~/.mq.
PROJECT_FILE = CONTEXT_DIR / "bridget-project"

_GIT_TIMEOUT = 5
_MAX_DIRTY_SHOWN = 5


def known_local_repos() -> dict[str, str]:
    """Read repo registry from MQ_MCP_LOCAL_REPOS (same logic as bridge.py)."""
    mcp_root = Path(__file__).resolve().parents[1]
    repos: dict[str, str] = {"mq-mcp": str(mcp_root)}
    raw = os.getenv("MQ_MCP_LOCAL_REPOS", "")
    for item in raw.split(","):
        item = item.strip()
        if item:
            p = Path(item).expanduser().resolve()
            repos[p.name] = str(p)
    return repos


# ----------------------------------------------------------------------
# Project pin
# ----------------------------------------------------------------------


def get_project() -> dict | None:
    """Return the pinned project ``{"name", "path"}`` or None."""
    if not PROJECT_FILE.exists():
        return None
    try:
        obj = json.loads(PROJECT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) and obj.get("path") else None


def set_project(name: str) -> dict | None:
    """Pin ``name`` (resolved via the repo registry). None if unknown/unwritable."""
    repos = known_local_repos()
    match = next((k for k in repos if k.lower() == name.lower()), None)
    if not match:
        return None
    entry = {"name": match, "path": repos[match]}
    try:
        PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROJECT_FILE.write_text(json.dumps(entry), encoding="utf-8")
    except OSError:
        return None
    return entry


def clear_project() -> None:
    """Remove the project pin. Never raises."""
    try:
        PROJECT_FILE.unlink()
    except OSError:
        pass


# ----------------------------------------------------------------------
# Git brief
# ----------------------------------------------------------------------


def _git(cwd: str | Path, args: list[str]) -> str | None:
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
    return result.stdout.strip()


def current_branch(path: str | Path) -> str | None:
    return _git(path, ["rev-parse", "--abbrev-ref", "HEAD"]) or None


def repo_brief(path: str | Path) -> str:
    """Short git brief: current branch + dirty-file count/sample.

    Returns a multi-line, indented string. Degrades gracefully when ``path`` is
    not a git repo (used both for --continue and for prompt injection).
    """
    branch = current_branch(path)
    status = _git(path, ["status", "--porcelain"])
    if branch is None and status is None:
        return "  (not a git repo)"
    lines = [f"  branch: {branch or '?'}"]
    dirty = [ln for ln in (status or "").splitlines() if ln.strip()]
    if dirty:
        # Porcelain is "XY <path>"; split off the status code rather than slicing
        # a fixed width — _git() strips the leading space off the first line.
        names = [ln.strip().split(None, 1)[-1] for ln in dirty[:_MAX_DIRTY_SHOWN]]
        more = len(dirty) - len(names)
        sample = ", ".join(names) + (f" (+{more})" if more > 0 else "")
        lines.append(f"  dirty: {len(dirty)} file(s) — {sample}")
    else:
        lines.append("  dirty: clean")
    return "\n".join(lines)


def last_review(path: str | Path) -> str | None:
    """Most recent review across all files in the project's review history.

    Best-effort: reads ``review_engine/memory/review_history.json`` directly so
    this stays decoupled from server.py. None when absent/unreadable.
    """
    hist = Path(path) / "review_engine" / "memory" / "review_history.json"
    if not hist.exists():
        return None
    try:
        data = json.loads(hist.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    newest: dict | None = None
    for entries in data.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if newest is None or entry.get("timestamp", 0) > newest.get("timestamp", 0):
                newest = entry
    if newest is None:
        return None
    return (
        f"  recent review: {newest.get('file_path', '?')} "
        f"@ {newest.get('timestamp_iso', '?')} "
        f"({newest.get('finding_count', '?')} findings)"
    )


# ----------------------------------------------------------------------
# System-prompt injection (used by run_bridge for a pinned project)
# ----------------------------------------------------------------------


def project_context_block() -> str:
    """Return a system-prompt block for the pinned project, or '' if none."""
    proj = get_project()
    if not proj:
        return ""
    return (
        "\n\n---\n"
        "## Pinned project\n\n"
        f"{proj['name']} ({proj['path']})\n"
        f"{repo_brief(proj['path'])}\n\n"
        "Treat this repo as the working context for this session.\n---\n"
    )


# ----------------------------------------------------------------------
# Command handlers (synchronous; print and return)
# ----------------------------------------------------------------------


def handle_history(limit: int = 20) -> None:
    entries = BridgetContext().read_history(limit=limit)
    if not entries:
        print("No session history yet.")
        return
    print(f"Bridget history (last {len(entries)}):")
    for e in entries:
        proj = e.get("project") or "-"
        summary = (e.get("summary") or "").strip() or "(no summary)"
        tools = e.get("tools") or []
        shown = tools[:_MAX_DIRTY_SHOWN]
        tools_s = ", ".join(shown) + (
            f" (+{len(tools) - len(shown)})" if len(tools) > len(shown) else ""
        ) if tools else "-"
        print(f"  {e.get('ts', '?')}  [{proj}]  {summary}")
        print(f"       tools: {tools_s}")


def handle_project(name: str | None) -> None:
    if not name:
        proj = get_project()
        if proj:
            print(f"Pinned project: {proj['name']} ({proj['path']})")
        else:
            print("No project pinned. Use: bridget --project <repo>")
        return
    entry = set_project(name)
    if entry is None:
        available = ", ".join(sorted(known_local_repos()))
        print(f"Unknown repo: '{name}'\nAvailable: {available}")
        return
    print(f"Pinned project: {entry['name']} ({entry['path']})")


def handle_continue() -> None:
    proj = get_project()
    if not proj:
        print("No project pinned. Use: bridget --project <repo> first.")
        return
    print(f"Continue — {proj['name']} ({proj['path']})")
    print(repo_brief(proj["path"]))
    print(last_review(proj["path"]) or "  recent review: none")


def maybe_handle_runtime_command(argv: list[str]) -> bool:
    """Handle --history / --continue / --project synchronously as a pre-flight.

    Returns True if a runtime command was handled (caller should exit), so these
    flags never reach the async bridge or the OpenAI/MCP path.
    """
    if "--history" in argv:
        i = argv.index("--history")
        limit = 20
        if i + 1 < len(argv) and argv[i + 1].isdigit():
            limit = int(argv[i + 1])
        handle_history(limit)
        return True
    if "--continue" in argv:
        handle_continue()
        return True
    if "--project" in argv:
        i = argv.index("--project")
        name = None
        if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            name = argv[i + 1]
        handle_project(name)
        return True
    return False
