"""
Repo Context Builder — mq-mcp review engine, Phase 2.1

Generates lightweight context artifacts for the review engine:

  architecture_map.json   — what each file IS (role/purpose), not just what it imports
  file_summary_index.json — per-file: docstring, public symbols, line count

Does NOT do full AST callgraph analysis. That is a later phase.
Designed to run fast (< 2s on mq-mcp scale), be re-run on every review,
and produce output that a review prompt can include directly.

Usage:
  python review_engine/repo_context_builder.py
  python review_engine/repo_context_builder.py --out /path/to/output/
"""

import ast
import json
import os
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

IGNORED_DIRS = {
    ".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "dist", "build", "backups",
    "semantic_memory",
}

IGNORED_FILES = {
    ".DS_Store", "uv.lock", "*.pyc",
}

# Role heuristics: (pattern_in_path → role label)
# Checked in order — first match wins.
ROLE_HEURISTICS: list[tuple[str, str]] = [
    ("server.py",           "MCP server — tool registry and HTTP endpoints"),
    ("bridge.py",           "orchestration layer — MCP ↔ LLM bridge"),
    ("ask.py",              "semantic memory — vector store querying"),
    ("bridget_voice.py",    "voice command handler — TTS and voice triggers"),
    ("main.py",             "CLI entry point"),
    ("mqlaunch.sh",         "interactive TUI launcher script"),
    ("review_engine/",      "review engine — context building and routing"),
    ("reviews/contracts/",  "review contract — hard rules for review output"),
    ("reviews/profiles/",   "review profile — mode and focus configuration"),
    ("reviews/skills/",     "review skill — file-type specific review guidance"),
    ("reviews/golden/",     "golden review — high-quality reference example"),
    ("docs/architecture/",  "architecture documentation"),
    ("docs/",               "documentation"),
    ("scripts/",            "automation script"),
    ("tests/",              "test file"),
    ("skills/",             "Claude Code subagent skill definition"),
    (".claude/agents/",     "Claude Code subagent definition"),
    (".github/workflows/",  "GitHub Actions CI workflow"),
    ("profiles/",           "MCP client profile template"),
    ("ROADMAP",             "project roadmap"),
    ("CHANGELOG",           "release changelog"),
    ("README",              "project readme"),
    ("SAFETY_MODEL",        "safety model documentation"),
    ("TOOL_INDEX",          "MCP tool index"),
    ("RUNBOOK",             "operational runbook"),
    ("pyproject.toml",      "Python project configuration"),
    (".env",                "environment variable configuration"),
]


def _role_for(rel_path: str) -> str:
    for pattern, role in ROLE_HEURISTICS:
        if pattern in rel_path:
            return role
    return "unknown"


def _extract_python_symbols(source: str) -> dict:
    """Extract module docstring and public top-level symbols from Python source."""
    result: dict = {"docstring": None, "functions": [], "classes": [], "constants": []}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return result

    result["docstring"] = ast.get_docstring(tree)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                result["functions"].append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                result["classes"].append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "line": node.lineno,
                })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    result["constants"].append(target.id)

    return result


def _file_summary(path: Path, rel: str) -> dict:
    summary: dict = {
        "path": rel,
        "role": _role_for(rel),
        "lines": 0,
        "size_bytes": path.stat().st_size,
    }

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        summary["lines"] = text.count("\n") + 1
    except Exception:
        return summary

    if path.suffix == ".py":
        symbols = _extract_python_symbols(text)
        summary["module_docstring"] = symbols["docstring"]
        summary["public_functions"] = [f["name"] for f in symbols["functions"]]
        summary["public_classes"] = [c["name"] for c in symbols["classes"]]
        summary["constants"] = symbols["constants"]
    elif path.suffix in {".md", ".txt"}:
        first_line = text.splitlines()[0].lstrip("#").strip() if text.strip() else ""
        summary["title"] = first_line or None

    return summary


def _should_ignore(rel: Path) -> bool:
    for part in rel.parts:
        if part in IGNORED_DIRS:
            return True
    name = rel.name
    if name.startswith(".") and name not in {".env", ".gitignore", ".markdownlint.json"}:
        return True
    return False


def build_context(
    repo_root: Path = REPO_ROOT,
    out_dir: Optional[Path] = None,
) -> dict:
    """
    Scan repo_root and produce architecture_map and file_summary_index.
    Returns both as dicts. Writes JSON files to out_dir if provided.
    """
    out_dir = out_dir or (repo_root / "review_engine" / "context")
    out_dir.mkdir(parents=True, exist_ok=True)

    architecture_map: dict[str, str] = {}
    file_summary_index: list[dict] = []

    root = repo_root.resolve()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if _should_ignore(rel):
            continue
        if len(rel.parts) > 6:
            continue

        rel_str = str(rel)
        role = _role_for(rel_str)
        architecture_map[rel_str] = role

        # Only build full summaries for code and docs — skip binary/data files
        if path.suffix in {".py", ".sh", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}:
            if path.stat().st_size < 500_000:  # skip huge JSON data files
                summary = _file_summary(path, rel_str)
                file_summary_index.append(summary)

    result = {
        "architecture_map": architecture_map,
        "file_summary_index": file_summary_index,
        "repo_root": str(root),
        "file_count": len(architecture_map),
    }

    arch_path = out_dir / "architecture_map.json"
    idx_path = out_dir / "file_summary_index.json"

    arch_path.write_text(
        json.dumps(architecture_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    idx_path.write_text(
        json.dumps(file_summary_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return result


def _context_summary(result: dict) -> str:
    """Return a short human-readable summary of what was built."""
    arch = result["architecture_map"]
    idx = result["file_summary_index"]

    py_files = [f for f in idx if f["path"].endswith(".py")]
    unknown = [p for p, r in arch.items() if r == "unknown"]

    lines = [
        f"repo_context_builder: {result['file_count']} files mapped",
        f"  Python files with symbol index: {len(py_files)}",
        f"  Files with unknown role: {len(unknown)}",
        f"  Output: {result['repo_root']}/review_engine/context/",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build repo context artifacts for the review engine.")
    parser.add_argument("--out", type=Path, default=None, help="Output directory (default: review_engine/context/)")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="Repo root path")
    parser.add_argument("--json", action="store_true", help="Print full JSON output instead of summary")
    args = parser.parse_args()

    result = build_context(repo_root=args.repo, out_dir=args.out)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_context_summary(result))
