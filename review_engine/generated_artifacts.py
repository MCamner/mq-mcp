"""
Generated Artifacts Builder — mq-mcp review engine, v1.6.0

Writes two rich JSON files to generated/architecture/ when build_repo_context runs:

  architecture_map.json  — schema architecture_map.v1
                           file path → {role, public_symbols, last_review_timestamp, hub_score}

  ownership_map.json     — schema ownership_map.v1
                           file path → {author, change_frequency, last_modified}

Both files are excluded from version control by generated/.gitignore.
Callers should not assume these files exist without running build_repo_context first.

Usage:
  from review_engine.generated_artifacts import build_rich_architecture_map, build_ownership_map
  build_rich_architecture_map(repo_root, out_dir)
  build_ownership_map(repo_root, out_dir)
"""

from __future__ import annotations

import ast
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

ARCHITECTURE_MAP_SCHEMA = "architecture_map.v1"
OWNERSHIP_MAP_SCHEMA = "ownership_map.v1"

# Cap git log history scan to keep build fast
_GIT_LOG_MAX_COMMITS = 200


# ── helpers ───────────────────────────────────────────────────────────────────

def _public_symbols(path: Path) -> list[str]:
    """Extract top-level public function and class names from a Python file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return []
    symbols: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                symbols.append(node.name)
    return symbols


def _last_review_timestamp(file_path: str, review_memory_path: Path) -> float | None:
    """Return the timestamp of the last review for this file, or None."""
    if not review_memory_path.exists():
        return None
    try:
        data: dict[str, list[dict]] = json.loads(
            review_memory_path.read_text(encoding="utf-8")
        )
        entries = data.get(file_path, [])
        if entries:
            return entries[0].get("timestamp")
    except Exception:
        pass
    return None


def _hub_scores(callgraph_path: Path) -> dict[str, int]:
    """Return {file_path: importer_count} from callgraph.json."""
    if not callgraph_path.exists():
        return {}
    try:
        cg = json.loads(callgraph_path.read_text(encoding="utf-8"))
        return {f: len(imp) for f, imp in cg.get("importers", {}).items()}
    except Exception:
        return {}


def _git_log_ownership(repo_root: Path) -> dict[str, dict[str, Any]]:
    """
    Run one git log call and parse per-file author, change_frequency, last_modified.
    Returns {file_path: {author, change_frequency, last_modified}} for repo-relative paths.
    """
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"-{_GIT_LOG_MAX_COMMITS}",
                "--no-merges",
                "--format=COMMIT|%an|%aI",
                "--name-only",
            ],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=15,
        )
        if result.returncode != 0:
            return {}
    except Exception:
        return {}

    # Parse: COMMIT|author|timestamp\n\nfile1\nfile2\n\nCOMMIT|...
    ownership: dict[str, dict[str, Any]] = {}
    author_counts: dict[str, Counter] = {}
    last_seen: dict[str, str] = {}

    current_author = ""
    current_ts = ""
    in_files = False

    for line in result.stdout.splitlines():
        if line.startswith("COMMIT|"):
            _, current_author, current_ts = line.split("|", 2)
            in_files = False
        elif line.strip() == "":
            in_files = True
        elif in_files and line.strip():
            rel = line.strip()
            author_counts.setdefault(rel, Counter())[current_author] += 1
            if rel not in last_seen:
                last_seen[rel] = current_ts  # first occurrence = most recent

    for rel, counts in author_counts.items():
        ownership[rel] = {
            "author": counts.most_common(1)[0][0] if counts else "unknown",
            "change_frequency": sum(counts.values()),
            "last_modified": last_seen.get(rel, ""),
        }

    return ownership


# ── public builders ───────────────────────────────────────────────────────────

def build_rich_architecture_map(
    repo_root: Path = REPO_ROOT,
    out_dir: Path | None = None,
    flat_arch_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Write generated/architecture/architecture_map.json (schema: architecture_map.v1).

    Enriches the flat architecture_map with:
    - public_symbols:          top-level public names from Python files
    - last_review_timestamp:   timestamp from review_engine/memory/review_history.json
    - hub_score:               importer count from review_engine/context/callgraph.json

    Args:
        repo_root:      Repo root path.
        out_dir:        Output directory. Defaults to generated/architecture/.
        flat_arch_map:  Pre-built {file_path: role_str} to avoid re-scanning.
                        If None, reads from review_engine/context/architecture_map.json.

    Returns the built dict.
    """
    out_dir = out_dir or (repo_root / "generated" / "architecture")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load flat map
    if flat_arch_map is None:
        flat_path = repo_root / "review_engine" / "context" / "architecture_map.json"
        try:
            flat_arch_map = json.loads(flat_path.read_text(encoding="utf-8"))
        except Exception:
            flat_arch_map = {}

    review_memory_path = repo_root / "review_engine" / "memory" / "review_history.json"
    callgraph_path = repo_root / "review_engine" / "context" / "callgraph.json"
    hub_scores = _hub_scores(callgraph_path)

    files: dict[str, Any] = {}
    for rel_str, role in flat_arch_map.items():
        path = repo_root / rel_str
        symbols = _public_symbols(path) if path.suffix == ".py" and path.exists() else []
        files[rel_str] = {
            "role": role,
            "public_symbols": symbols,
            "last_review_timestamp": _last_review_timestamp(rel_str, review_memory_path),
            "hub_score": hub_scores.get(rel_str, 0),
        }

    result: dict[str, Any] = {
        "schema": ARCHITECTURE_MAP_SCHEMA,
        "repo_name": repo_root.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "files": files,
    }

    out_path = out_dir / "architecture_map.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def build_ownership_map(
    repo_root: Path = REPO_ROOT,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Write generated/architecture/ownership_map.json (schema: ownership_map.v1).

    Per file: most frequent author, commit count (change_frequency), last commit ISO date.
    Reads last _GIT_LOG_MAX_COMMITS commits. Files with no git history are omitted.

    Returns the built dict.
    """
    out_dir = out_dir or (repo_root / "generated" / "architecture")
    out_dir.mkdir(parents=True, exist_ok=True)

    ownership = _git_log_ownership(repo_root)

    result: dict[str, Any] = {
        "schema": OWNERSHIP_MAP_SCHEMA,
        "repo_name": repo_root.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(ownership),
        "files": ownership,
    }

    out_path = out_dir / "ownership_map.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
