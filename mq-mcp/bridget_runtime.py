"""
bridget_runtime.py — Bridget Runtime helpers for --project / --history / --continue / --forget.

Self-contained: pure helpers plus synchronous command handlers that print and
return. No OpenAI client and no MCP session are needed, so bridge.py intercepts
these flags before the async bridge starts (same pattern as --workflow).

Boundary: this only *reads, pins, and deletes session context* (project, git
state, prior sessions, last review). It never writes learning or promotes
anything — sessions are context, not evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from bridget_context import CONTEXT_DIR, BridgetContext
import learn_engine

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


def _last_review_entry(path: str | Path) -> dict | None:
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
            if isinstance(entry, dict) and (
                newest is None or entry.get("timestamp", 0) > newest.get("timestamp", 0)
            ):
                newest = entry
    return newest


def git_diff_brief(path: str | Path) -> str:
    """Short read-only recent-work hint from the current git diff."""
    out = _git(path, ["diff", "--name-only"])
    files = [ln for ln in (out or "").splitlines() if ln.strip()]
    if not files:
        return "  recent work: no unstaged diff"
    shown = files[:_MAX_DIRTY_SHOWN]
    more = len(files) - len(shown)
    suffix = f" (+{more})" if more > 0 else ""
    return f"  recent work: {', '.join(shown)}{suffix}"


# ----------------------------------------------------------------------
# System-prompt injection (used by run_bridge)
# ----------------------------------------------------------------------


def project_context_block() -> str:
    """Return a system-prompt repo context block.

    A pinned project wins. Without one, Bridget auto-detects the current git
    root so one-shot calls launched inside a repo still start informed.
    """
    proj = get_project()
    source = "pinned"
    if not proj:
        root = _git(Path.cwd(), ["rev-parse", "--show-toplevel"])
        if not root:
            return ""
        proj = {"name": Path(root).name, "path": root}
        source = "auto-detected"
    review = last_review(proj["path"]) or "  recent review: none"
    return (
        "\n\n---\n"
        f"## Working repo ({source})\n\n"
        f"{proj['name']} ({proj['path']})\n"
        f"{repo_brief(proj['path'])}\n"
        f"{git_diff_brief(proj['path'])}\n"
        f"{review}\n\n"
        "Treat this repo as the working context for this session.\n---\n"
    )


# ----------------------------------------------------------------------
# Command handlers (synchronous; print and return)
# ----------------------------------------------------------------------


def _session_kind(entry: dict) -> str:
    """A short ` (REPL, N turns)` tag for chat sessions; empty for one-shot.

    Reads the Phase-4 metadata written only for REPL sessions, so one-shot
    history lines render exactly as before.
    """
    if not entry.get("chat_mode"):
        return ""
    turns = entry.get("turns")
    turn_part = f", {turns} turns" if isinstance(turns, int) else ""
    return f" (REPL{turn_part})"


def _last_session(entries: list[dict]) -> dict | None:
    """Most recent REPL session if any, else the most recent session overall.

    ``entries`` is newest-first (as returned by ``read_history``).
    """
    if not entries:
        return None
    for e in entries:
        if e.get("chat_mode"):
            return e
    return entries[0]


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
        kind = _session_kind(e)
        print(f"  {e.get('ts', '?')}  [{proj}]{kind}  {summary}")
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
    # Surface the previous session first — a REPL session if there was one — so
    # --continue resumes the last interactive thread even when no project is
    # pinned. read_history is newest-first and tolerates a missing log.
    last = _last_session(BridgetContext().read_history(limit=20))
    if last:
        kind = _session_kind(last) or " (one-shot)"
        prompt = (last.get("prompt") or "").strip() or "(no prompt)"
        summary = (last.get("summary") or "").strip() or "(no summary)"
        print(f"Last session {last.get('ts', '?')}{kind}")
        print(f"  prompt:  {prompt}")
        print(f"  summary: {summary}")

    proj = get_project()
    if not proj:
        print("No project pinned. Use: bridget --project <repo> first.")
        return
    print(f"Continue — {proj['name']} ({proj['path']})")
    print(repo_brief(proj["path"]))
    print(last_review(proj["path"]) or "  recent review: none")


def handle_forget(date: str | None) -> None:
    if not date:
        print("Usage: bridget --forget YYYY-MM-DD")
        return
    try:
        removed = BridgetContext().forget_day(date)
    except ValueError as exc:
        print(f"Could not forget sessions: {exc}")
        return
    if removed:
        print(f"Forgot {removed} Bridget session(s) from {date}.")
    else:
        print(f"No Bridget sessions found for {date}.")


def _current_repo() -> dict | None:
    proj = get_project()
    if proj:
        return proj
    root = _git(Path.cwd(), ["rev-parse", "--show-toplevel"])
    if not root:
        return None
    return {"name": Path(root).name, "path": root}


def handle_learn_last() -> None:
    repo = _current_repo()
    if not repo:
        print("No git repo detected and no project pinned.")
        return
    root = Path(repo["path"])
    diff_files = [ln for ln in (_git(root, ["diff", "--name-only"]) or "").splitlines() if ln.strip()]
    review = _last_review_entry(root)
    if diff_files:
        source = "diff"
        task = f"review recent diff in {repo['name']}"
        lesson = f"Recent work touched: {', '.join(diff_files[:5])}"
        validation = [f"git diff --name-only: {item}" for item in diff_files[:5]]
        files = diff_files[:10]
    elif review:
        source = "review"
        file_path = str(review.get("file_path") or "unknown")
        task = f"review {file_path}"
        lesson = str(review.get("summary") or f"Review findings for {file_path}")
        validation = [last_review(root) or f"last review: {file_path}"]
        files = [file_path]
    else:
        print("No recent diff or review history found to draft from.")
        return

    record = learn_engine.make_learning(
        root,
        repo=repo["name"],
        source=source,
        task=task,
        lesson=lesson,
        validation=validation,
        files_touched=files,
        tags=["bridget-preview", "learning-origin:bridget", source],
        risk="unknown",
    ).to_dict()
    preview = {
        "status": "preview",
        "write_performed": False,
        "learning_origin": "bridget",
        "storage": "not stored; call approved learn tool after review",
        "record": record,
    }
    print(json.dumps(learn_engine.redact_secrets(preview), ensure_ascii=False, indent=2))


def handle_dashboard() -> None:
    metrics = BridgetContext().metrics()
    totals = metrics["totals"]
    print("Bridget dashboard:")
    print(f"  sessions: {totals['sessions']} ({totals['chat_sessions']} chat)")
    print(f"  tool calls: {totals['tool_calls']}")
    print(f"  delegations: {totals['delegations']}")
    print(f"  learning suggestions: {totals['learning_suggestions']}")
    print(f"  accepted learning: {totals['accepted_learning']}")
    print(f"  history hits: {totals['history_hits']}")
    print(f"  context hits: {totals['context_hits']}")
    if metrics["by_day"]:
        print("  by day:")
        for day, row in sorted(metrics["by_day"].items())[-7:]:
            print(
                f"    {day}: sessions {row['sessions']}, tools {row['tool_calls']}, "
                f"delegations {row['delegations']}, learn suggestions {row['learning_suggestions']}"
            )


def maybe_handle_runtime_command(argv: list[str]) -> bool:
    """Handle --history / --continue / --project / --forget as a pre-flight.

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
    if "--forget" in argv:
        i = argv.index("--forget")
        date = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else None
        handle_forget(date)
        return True
    if "--learn-last" in argv:
        handle_learn_last()
        return True
    if "--dashboard" in argv:
        handle_dashboard()
        return True
    if "--project" in argv:
        i = argv.index("--project")
        name = None
        if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            name = argv[i + 1]
        handle_project(name)
        return True
    return False
