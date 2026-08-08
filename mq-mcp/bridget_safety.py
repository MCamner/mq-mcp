"""Safety lookup for Bridget's approval gate.

Thin, pure helper: reads the repo's machine-readable tool contract
(docs/tool_contracts.json) and decides which tool calls need human consent
before they run.

This is a *consent shim*, not a policy source. The classification lives in
docs/tool_contracts.json (kept in sync with docs/TOOL_SAFETY.md and server.py);
this module only reads it.
"""

import json
from pathlib import Path

# bridget_safety.py lives in <repo>/mq-mcp/; contracts live in <repo>/docs/.
REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTRACTS_PATH = REPO_ROOT / "docs" / "tool_contracts.json"

# Class D tools whose whole effect is on screen and gone the moment it is over:
# no file written, no process left behind, no state changed. Gating these would
# put a prompt in front of Bridget adjusting the volume or speaking a sentence,
# which is how an approval prompt turns into something you dismiss unread.
_COSMETIC_TOOLS = frozenset({
    "lock_screen",
    "open_app",
    "open_chrome",
    "open_finder",
    "open_messages",
    "open_spotify",
    "open_url",
    "open_vscode",
    "set_volume",
    "show_notification",
    "speak_text",
    "toggle_dark_mode",
})


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

    Gate on effect, not on class: 27 Class A/B tools (git_status, git_diff,
    check_port, get_battery_status …) shell out while being strictly read-only,
    so `subprocess` on its own would interrupt ordinary reads. What earns a
    prompt is a tool that writes, or a Class D tool that runs something —
    minus the cosmetic ones. Unknown tools are gated: the gate never silently
    runs what it cannot classify.
    """
    meta = smap.get(name)
    if meta is None:
        return True
    if meta.get("write"):
        return True
    return meta.get("class") == "D" and name not in _COSMETIC_TOOLS
