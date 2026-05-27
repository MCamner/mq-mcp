"""
Callgraph Builder — mq-mcp review engine, Phase 2.2

Builds a cross-file import graph and symbol index for the repo. This is the
symbolic intelligence layer: it answers "which files depend on which" and
"which files are the most imported (hub files)" — enabling cross-file context
injection during deep reviews.

Output: review_engine/context/callgraph.json

Schema:
  imports    — per repo-relative file, list of repo-relative files it imports
  importers  — reverse index: per file, list of files that import it
  hub_files  — files with 3+ importers (high-connectivity, review first)
  symbols    — per file, top-level public function and class names
  edges      — full edge list: {from, to, import_names}

Import resolution: converts Python dotted module names to repo-relative paths.
stdlib and third-party modules are excluded (not resolvable to repo files).
Shell and other non-Python files are excluded from the call graph but included
in the symbol index as name-only entries.

Usage:
  python review_engine/callgraph_builder.py
  python review_engine/callgraph_builder.py --repo /path/to/repo
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

IGNORED_DIRS = {
    ".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "dist", "build", "backups",
    "semantic_memory", "review_engine/context",
}

HUB_THRESHOLD = 2  # files imported by this many or more files are hubs


@dataclass
class ImportEdge:
    from_file: str      # repo-relative path
    to_file: str        # repo-relative path
    import_names: list[str] = field(default_factory=list)  # names imported from to_file


class CallgraphBuilder:
    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self._root = repo_root.resolve()
        self._out_dir = self._root / "review_engine" / "context"

    # ── file discovery ────────────────────────────────────────────────────────

    def _python_files(self) -> list[Path]:
        files: list[Path] = []
        for p in sorted(self._root.rglob("*.py")):
            try:
                rel = p.relative_to(self._root)
            except ValueError:
                continue
            if any(part in IGNORED_DIRS for part in rel.parts):
                continue
            if len(rel.parts) > 7:
                continue
            files.append(p)
        return files

    # ── module → file resolution ──────────────────────────────────────────────

    def _module_index(self, python_files: list[Path]) -> dict[str, str]:
        """Build dotted-module-name → repo-relative-path index."""
        index: dict[str, str] = {}
        for p in python_files:
            rel = p.relative_to(self._root)
            # e.g. review_engine/severity_engine.py → review_engine.severity_engine
            module = ".".join(rel.with_suffix("").parts)
            index[module] = str(rel)
            # also index by basename without suffix for simple imports
            index[rel.stem] = str(rel)
        return index

    def _resolve_module(self, module: str, module_index: dict[str, str]) -> Optional[str]:
        """Resolve a dotted module name to a repo-relative file path, or None."""
        if module in module_index:
            return module_index[module]
        # try parent packages
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in module_index:
                return module_index[candidate]
        return None

    # ── AST import extraction ─────────────────────────────────────────────────

    def _extract_imports(
        self,
        source: str,
        from_file: str,
        module_index: dict[str, str],
    ) -> list[ImportEdge]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        edges: list[ImportEdge] = []
        seen: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = self._resolve_module(alias.name, module_index)
                    if target and target not in seen and target != from_file:
                        edges.append(ImportEdge(
                            from_file=from_file,
                            to_file=target,
                            import_names=[alias.asname or alias.name],
                        ))
                        seen.add(target)

            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                target = self._resolve_module(node.module, module_index)
                if target and target not in seen and target != from_file:
                    names = [a.name for a in node.names if a.name != "*"]
                    edges.append(ImportEdge(
                        from_file=from_file,
                        to_file=target,
                        import_names=names,
                    ))
                    seen.add(target)

        return edges

    # ── symbol extraction ─────────────────────────────────────────────────────

    def _extract_symbols(self, source: str) -> list[str]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        symbols: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not node.name.startswith("_"):
                    symbols.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    symbols.append(node.name)
        return symbols

    # ── main build ────────────────────────────────────────────────────────────

    def build(self) -> dict:
        python_files = self._python_files()
        module_index = self._module_index(python_files)

        all_edges: list[ImportEdge] = []
        symbols: dict[str, list[str]] = {}

        for p in python_files:
            rel = str(p.relative_to(self._root))
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            all_edges.extend(
                self._extract_imports(source, rel, module_index)
            )
            symbols[rel] = self._extract_symbols(source)

        # Build imports map: from_file → [to_file, ...]
        imports: dict[str, list[str]] = {}
        for edge in all_edges:
            imports.setdefault(edge.from_file, [])
            if edge.to_file not in imports[edge.from_file]:
                imports[edge.from_file].append(edge.to_file)

        # Build importers map (reverse)
        importers: dict[str, list[str]] = {}
        for from_f, targets in imports.items():
            for to_f in targets:
                importers.setdefault(to_f, [])
                if from_f not in importers[to_f]:
                    importers[to_f].append(from_f)

        # Hub files
        hub_files = sorted(
            f for f, imp in importers.items() if len(imp) >= HUB_THRESHOLD
        )

        # Edge list (serializable)
        edges = [
            {
                "from": e.from_file,
                "to": e.to_file,
                "import_names": e.import_names,
            }
            for e in all_edges
        ]

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(self._root),
            "file_count": len(python_files),
            "hub_threshold": HUB_THRESHOLD,
            "imports": imports,
            "importers": importers,
            "hub_files": hub_files,
            "symbols": symbols,
            "edges": edges,
        }

        self._out_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._out_dir / "callgraph.json"
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return result

    def format_summary(self, result: dict) -> str:
        n_files = result["file_count"]
        n_edges = len(result["edges"])
        hubs = result["hub_files"]
        hub_str = ", ".join(Path(h).name for h in hubs[:5])
        if len(hubs) > 5:
            hub_str += f" … (+{len(hubs) - 5} more)"
        lines = [
            f"callgraph_builder: {n_files} Python files  {n_edges} import edges",
            f"  Hub files ({len(hubs)}): {hub_str or 'none'}",
            f"  Output: review_engine/context/callgraph.json",
        ]
        return "\n".join(lines)

    def cross_file_context(self, rel_path: str, max_items: int = 5) -> str:
        """Return a short cross-file context block for injection into a review prompt.

        Shows what the file imports (its dependencies) and what imports it
        (its dependents), capped at max_items each.
        """
        cg_path = self._out_dir / "callgraph.json"
        if not cg_path.exists():
            return ""
        try:
            data = json.loads(cg_path.read_text(encoding="utf-8"))
        except Exception:
            return ""

        # Normalize path separators
        rel = rel_path.replace("\\", "/")

        deps = data.get("imports", {}).get(rel, [])[:max_items]
        dependents = data.get("importers", {}).get(rel, [])[:max_items]
        is_hub = rel in data.get("hub_files", [])

        if not deps and not dependents:
            return ""

        lines = ["## Cross-file context"]
        if is_hub:
            n_importers = len(data.get("importers", {}).get(rel, []))
            lines.append(f"Hub file — imported by {n_importers} files in this repo.")
        if deps:
            lines.append(f"Imports: {', '.join(Path(d).name for d in deps)}")
        if dependents:
            lines.append(f"Imported by: {', '.join(Path(d).name for d in dependents)}")

        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Build cross-file import graph for the review engine."
    )
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="Print full JSON output")
    args = parser.parse_args()

    builder = CallgraphBuilder(repo_root=args.repo)
    result = builder.build()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(builder.format_summary(result))
