"""Safety-class lookup for Bridget's approval gate.

Thin, pure helper: reads the repo's machine-readable tool contract
(docs/tool_contracts.json) and exposes per-tool safety class and write/
subprocess flags. The bridge uses this to decide whether a tool call needs
human approval (Class C/D) before running.

This is a *consent shim*, not a policy source. The classification lives in
docs/tool_contracts.json (kept in sync with docs/TOOL_SAFETY.md and server.py);
this module only reads it.
"""

import json
from pathlib import Path

# bridget_safety.py lives in <repo>/mq-mcp/; contracts live in <repo>/docs/.
REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTRACTS_PATH = REPO_ROOT / "docs" / "tool_contracts.json"

# Class C (writes files) and D (subprocess / opens apps) require explicit human
# approval. A (read-only repo-scoped) and B (read-only allowed paths) pass.
_APPROVAL_CLASSES = {"C", "D"}


def load_safety_map(path: Path | None = None) -> dict[str, dict]:
    """Build tool_name -> {"class", "write", "subprocess"} from the contract.

    Returns an empty map if the contract is missing or unparseable; callers
    treat an unknown tool as needing approval (fail-safe), so a missing file
    degrades to "ask about everything" rather than "run everything".
    """
    contracts_path = path or _CONTRACTS_PATH
    try:
        data = json.loads(contracts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    smap: dict[str, dict] = {}
    for tool in data.get("tools", []):
        name = tool.get("name")
        if not name:
            continue
        smap[name] = {
            "class": tool.get("safety_class") or tool.get("class") or "unknown",
            "write": bool(tool.get("write", False)),
            "subprocess": bool(tool.get("subprocess", False)),
        }
    return smap


def tool_class(name: str, smap: dict[str, dict]) -> str:
    """Safety class for a tool: "A".."D", or "unknown" if absent."""
    return smap.get(name, {}).get("class", "unknown")


def needs_approval(name: str, smap: dict[str, dict]) -> bool:
    """True when a tool call must be approved before it runs.

    Class C/D require approval. Unknown tools (not in the contract) are treated
    as requiring approval too: the gate never silently runs something it cannot
    classify.
    """
    cls = tool_class(name, smap)
    if cls == "unknown":
        return True
    return cls in _APPROVAL_CLASSES
