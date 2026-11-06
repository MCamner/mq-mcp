#!/usr/bin/env python3
"""Regenerate the tool grid and its numbers on docs/index.html.

Reads docs/tool_contracts.json through the same consent rule the bridge uses
(mq-mcp/bridget_safety.py) and rewrites everything between the tool-grid
markers, plus every data-stat value on the page. tests/test_pages_index.py
fails when the page and the contract disagree; run this to bring them back.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

from bridget_safety import load_safety_map, needs_approval, tool_class  # noqa: E402

PAGE = ROOT / "docs" / "index.html"
START = "<!-- tool-grid:start (scripts/render-pages-tool-grid.py) -->\n"
END = "<!-- tool-grid:end -->"

CLASSES = {
    "A": ("Read-only, repo-scoped", "Cannot write files. Subprocesses only through a fixed, contract-declared read-only boundary."),
    "B": ("Read-only, allowed paths", "Cannot write files. Reads outside the repo only where MQ_MCP_ALLOWED_PATHS permits."),
    "C": ("Write-capable, scoped", "Can modify files in the repo or in explicitly allowed paths. Always asks first."),
    "D": ("Subprocess and apps", "Run external processes or open applications. Asks first, except tools that only affect the screen."),
}


def render_grid(smap: dict[str, dict]) -> str:
    rows = []
    for cls, (title, desc) in CLASSES.items():
        names = sorted(n for n in smap if tool_class(n, smap) == cls)
        gated = sum(needs_approval(n, smap) for n in names)
        cells = "".join(
            f'<span class="cell" data-tool="{n}" data-class="{cls}" '
            f'data-gated="{"yes" if needs_approval(n, smap) else "no"}" title="{n}"></span>'
            for n in names
        )
        rows.append(
            f"""      <div class="class-row">
        <div>
          <div class="class-name">Class {cls}</div>
          <h3>{title}</h3>
          <p>{desc}</p>
          <div class="counts"><span data-stat="class-{cls.lower()}">{len(names)}</span> tools, <span data-stat="class-{cls.lower()}-gated">{gated}</span> ask first</div>
        </div>
        <div class="cells">{cells}</div>
      </div>
"""
        )
    return "".join(rows)


def main() -> int:
    smap = load_safety_map()
    unknown = {tool_class(n, smap) for n in smap} - set(CLASSES)
    if unknown:
        print(f"unknown safety classes: {sorted(unknown)}; add them to CLASSES", file=sys.stderr)
        return 1

    html = PAGE.read_text(encoding="utf-8")
    start, end = html.index(START) + len(START), html.index(END)
    html = html[:start] + render_grid(smap) + html[end:]

    stats = {
        "total": str(len(smap)),
        "gated": str(sum(needs_approval(n, smap) for n in smap)),
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    }
    for key, value in stats.items():
        html = re.sub(rf'(data-stat="{key}"[^>]*>)[^<]*(<)', rf"\g<1>{value}\g<2>", html)

    PAGE.write_text(html, encoding="utf-8")
    print(f"docs/index.html: {stats['total']} tools, {stats['gated']} gated, version {stats['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
