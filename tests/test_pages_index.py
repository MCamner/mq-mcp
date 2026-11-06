"""Keep the public Pages front page in step with the tool contract.

docs/index.html once said "All tools are sandboxed to the repository root"
and listed 13 tools, long after the contract held 143 tools in four safety
classes. The numbers on the page are tagged with data-stat and checked here
against docs/tool_contracts.json through the same rule the bridge uses.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

from bridget_safety import load_safety_map, needs_approval, tool_class  # noqa: E402

PAGE = ROOT / "docs" / "index.html"
FIX = "run: python3 scripts/render-pages-tool-grid.py"


def _page_stats() -> dict[str, str]:
    html = PAGE.read_text(encoding="utf-8")
    return dict(re.findall(r'data-stat="([a-z0-9-]+)"[^>]*>([^<]+)<', html))


def _expected_stats() -> dict[str, str]:
    smap = load_safety_map()
    total: Counter[str] = Counter()
    gated: Counter[str] = Counter()
    for name in smap:
        cls = tool_class(name, smap)
        total[cls] += 1
        gated[cls] += needs_approval(name, smap)
    stats = {
        "total": str(len(smap)),
        "gated": str(sum(gated.values())),
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    }
    for cls in total:
        stats[f"class-{cls.lower()}"] = str(total[cls])
        stats[f"class-{cls.lower()}-gated"] = str(gated[cls])
    return stats


def test_page_numbers_match_tool_contract() -> None:
    page = _page_stats()
    expected = _expected_stats()
    missing = sorted(set(expected) - set(page))
    assert not missing, f"docs/index.html lacks data-stat for {missing}; {FIX}"
    wrong = {k: (page[k], v) for k, v in expected.items() if page[k] != v}
    assert not wrong, f"docs/index.html (page, contract): {wrong}; {FIX}"


def test_page_tool_grid_matches_tool_contract() -> None:
    html = PAGE.read_text(encoding="utf-8")
    cells = re.findall(r'data-tool="([a-z0-9_]+)" data-class="([A-D])" data-gated="(yes|no)"', html)
    smap = load_safety_map()
    expected = {
        (name, tool_class(name, smap), "yes" if needs_approval(name, smap) else "no")
        for name in smap
    }
    assert len(cells) == len(set(cells)), "duplicate tool cells on the page"
    assert set(cells) == expected, (
        f"page only: {sorted(set(cells) - expected)}; "
        f"contract only: {sorted(expected - set(cells))}; {FIX}"
    )


def test_page_drops_retired_sandbox_claim() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert "sandboxed to the repository root" not in html
