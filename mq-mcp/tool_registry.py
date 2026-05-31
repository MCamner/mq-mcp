"""Tool registry for mq-mcp.

Loads tool metadata from docs/tool_contracts.json, normalizes field names,
infers missing metadata, and exports machine-readable artifacts.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS_PATH = _ROOT / "docs" / "tool_contracts.json"
_SERVER_PATH = _ROOT / "mq-mcp" / "server.py"
_GENERATED_DIR = _ROOT / "generated"

# ---------------------------------------------------------------------------
# Static metadata that cannot be reliably inferred from contracts alone
# ---------------------------------------------------------------------------

_CATEGORIES: dict[str, str] = {
    # repo
    "read_repo_file": "repo",
    "list_repo_files": "repo",
    "search_repo": "repo",
    "git_status": "repo",
    "git_diff": "repo",
    "update_repo_file": "repo",
    "analyze_csv": "repo",
    "export_symbol_index": "repo",
    "validate_project": "repo",
    # review
    "review_file": "review",
    "review_diff": "review",
    "review_repo": "review",
    "risk_review_file": "review",
    "risk_review_diff": "review",
    "get_last_review": "review",
    "list_review_contracts": "review",
    "list_review_history": "review",
    "list_review_skills": "review",
    "build_repo_context": "review",
    "detect_architecture_drift": "review",
    "review_runtime_contract": "review",
    "validate_orchestration_contract": "review",
    "review_architecture_doc": "review",
    # architecture
    "list_architecture_decisions": "architecture",
    "get_architecture_decision": "architecture",
    "record_architecture_decision": "architecture",
    "list_architecture_docs": "architecture",
    "extract_coding_conventions": "architecture",
    # memory
    "store_semantic_memory": "memory",
    "search_semantic_memory": "memory",
    "get_semantic_memory": "memory",
    "list_semantic_memory": "memory",
    "bootstrap_semantic_memory": "memory",
    # learn
    "get_learning": "learn",
    "list_learnings": "learn",
    "promote_learning": "learn",
    "search_learnings": "learn",
    "summarize_learnings": "learn",
    "record_learning": "learn",
    # integration
    "hal_repo_report": "integration",
    "repo_signal_analyze": "integration",
    "repo_signal_checklist": "integration",
    "repo_signal_doctor_json": "integration",
    "repo_signal_inspect": "integration",
    "repo_signal_status": "integration",
    # system
    "get_system_resources": "system",
    "get_battery_status": "system",
    "get_wifi_info": "system",
    "get_public_ip": "system",
    "list_running_apps": "system",
    "check_port": "system",
    "find_large_files": "system",
    "find_recent_files": "system",
    "list_local_repos": "system",
    # macos
    "open_app": "macos",
    "open_chrome": "macos",
    "open_finder": "macos",
    "open_messages": "macos",
    "open_spotify": "macos",
    "open_terminal": "macos",
    "open_vscode": "macos",
    "open_url": "macos",
    "open_in_app": "macos",
    "open_repo_terminal": "macos",
    "lock_screen": "macos",
    "set_volume": "macos",
    "set_wallpaper": "macos",
    "toggle_dark_mode": "macos",
    "show_notification": "macos",
    "speak_text": "macos",
    "create_note": "macos",
    "set_reminder": "macos",
    "take_screenshot": "macos",
    "get_todays_events": "macos",
    "list_openable_apps": "macos",
    "get_clipboard": "macos",
    "set_clipboard": "macos",
    # local
    "analyze_guitar_pro": "local",
    "edit_image": "local",
    # shell
    "run_tests": "shell",
    "run_mqlaunch": "shell",
    "run_mqlaunch_ask": "shell",
    "run_mqlaunch_bundle": "shell",
    "run_mqlaunch_demo": "shell",
    "run_mqlaunch_doctor": "shell",
    "run_mqlaunch_perf": "shell",
    "run_mqlaunch_release_check": "shell",
    "run_mqlaunch_selftest": "shell",
    "run_mqlaunch_system_check": "shell",
    "run_mqlaunch_version": "shell",
    # meta
    "tool_safety_report": "meta",
}

# Tools that require OPENAI_API_KEY
_REQUIRES_API_KEY: frozenset[str] = frozenset({
    "review_file",
    "review_diff",
    "review_repo",
    "risk_review_file",
    "risk_review_diff",
    "review_architecture_doc",
    "review_runtime_contract",
    "extract_coding_conventions",
    "summarize_learnings",
    "record_learning",
})

# Tools that use a network connection
_USES_NETWORK: frozenset[str] = frozenset(_REQUIRES_API_KEY | {
    "get_public_ip",
    "get_wifi_info",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _runtime_tool_names() -> list[str]:
    """Return tool names discovered via AST from server.py."""
    src = _SERVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)

    def is_mcp_tool(node: Any) -> bool:
        if isinstance(node, ast.Call):
            node = node.func
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "tool"
            and isinstance(node.value, ast.Name)
            and node.value.id == "mcp"
        )

    return sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(is_mcp_tool(d) for d in node.decorator_list)
    )


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw tool_contracts entry to the registry schema."""
    name = raw["name"]
    safety_class = raw.get("class", raw.get("safety_class", "?"))
    writes = bool(raw.get("write", raw.get("writes_files", False)))
    uses_sub = bool(raw.get("subprocess", raw.get("uses_subprocess", False)))
    return {
        "name": name,
        "category": _CATEGORIES.get(name, "other"),
        "safety_class": safety_class,
        "read_only": not writes,
        "writes_files": writes,
        "uses_subprocess": uses_sub,
        "uses_network": name in _USES_NETWORK,
        "requires_api_key": name in _REQUIRES_API_KEY,
        "resolver": raw.get("resolver", "none"),
        "description": raw.get("description", ""),
        "side_effects": raw.get("side_effects", []),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_registry() -> list[dict[str, Any]]:
    """Load and normalize all tools from tool_contracts.json."""
    data = json.loads(_CONTRACTS_PATH.read_text(encoding="utf-8"))
    return [_normalize(t) for t in data["tools"]]


def registry_summary() -> dict[str, Any]:
    """Return a summary dict: counts, version, safety class breakdown."""
    raw = json.loads(_CONTRACTS_PATH.read_text(encoding="utf-8"))
    tools = load_registry()
    classes: dict[str, int] = {}
    categories: dict[str, int] = {}
    for t in tools:
        cls = t["safety_class"]
        cat = t["category"]
        classes[cls] = classes.get(cls, 0) + 1
        categories[cat] = categories.get(cat, 0) + 1
    return {
        "schema_version": raw.get("schema_version"),
        "mq_mcp_version": raw.get("mq_mcp_version"),
        "tool_count": len(tools),
        "safety_classes": dict(sorted(classes.items())),
        "categories": dict(sorted(categories.items())),
        "api_key_required": sum(1 for t in tools if t["requires_api_key"]),
        "write_capable": sum(1 for t in tools if t["writes_files"]),
        "subprocess_capable": sum(1 for t in tools if t["uses_subprocess"]),
    }


def as_markdown_table() -> str:
    """Return all tools as a Markdown table sorted by category then name."""
    tools = sorted(load_registry(), key=lambda t: (t["category"], t["name"]))
    header = "| Tool | Category | Class | R/W | API key | Description |"
    sep    = "| ---- | -------- | ----- | --- | ------- | ----------- |"
    rows = []
    for t in tools:
        rw = "R" if t["read_only"] else "W"
        api = "yes" if t["requires_api_key"] else "no"
        desc = t["description"][:60] + "…" if len(t["description"]) > 60 else t["description"]
        rows.append(
            f"| `{t['name']}` | {t['category']} | {t['safety_class']}"
            f" | {rw} | {api} | {desc} |"
        )
    return "\n".join([header, sep] + rows)


# ---------------------------------------------------------------------------
# Generated artifact writers
# ---------------------------------------------------------------------------

def _ensure_generated() -> None:
    _GENERATED_DIR.mkdir(exist_ok=True)


def export_tool_index(path: Path | None = None) -> Path:
    """Write generated/tool-index.json and return the path."""
    _ensure_generated()
    out = path or _GENERATED_DIR / "tool-index.json"
    payload = {
        "schema": "tool-index.v1",
        "generated_from": "docs/tool_contracts.json",
        **registry_summary(),
        "tools": load_registry(),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def export_tool_safety(path: Path | None = None) -> Path:
    """Write generated/tool-safety.json with safety-focused view."""
    _ensure_generated()
    out = path or _GENERATED_DIR / "tool-safety.json"
    tools = load_registry()
    payload = {
        "schema": "tool-safety.v1",
        "generated_from": "docs/tool_contracts.json",
        "tool_count": len(tools),
        "tools": [
            {
                "name": t["name"],
                "safety_class": t["safety_class"],
                "category": t["category"],
                "read_only": t["read_only"],
                "writes_files": t["writes_files"],
                "uses_subprocess": t["uses_subprocess"],
                "uses_network": t["uses_network"],
                "requires_api_key": t["requires_api_key"],
                "resolver": t["resolver"],
                "side_effects": t["side_effects"],
            }
            for t in sorted(tools, key=lambda x: (x["safety_class"], x["name"]))
        ],
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def export_runtime_contract(path: Path | None = None) -> Path:
    """Write generated/runtime-contract.json with the runtime state snapshot."""
    _ensure_generated()
    out = path or _GENERATED_DIR / "runtime-contract.json"
    summary = registry_summary()
    runtime_names = _runtime_tool_names()
    payload = {
        "schema": "runtime-contract.v1",
        "mq_mcp_version": summary["mq_mcp_version"],
        "tool_count": len(runtime_names),
        "tool_count_contracts": summary["tool_count"],
        "safety_classes": summary["safety_classes"],
        "categories": summary["categories"],
        "runtime_tools": runtime_names,
        "write_capable_tools": [
            t["name"] for t in load_registry() if t["writes_files"]
        ],
        "subprocess_tools": [
            t["name"] for t in load_registry() if t["uses_subprocess"]
        ],
        "api_key_tools": [
            t["name"] for t in load_registry() if t["requires_api_key"]
        ],
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def export_release_state(path: Path | None = None) -> Path:
    """Write generated/release-state.json with current version and tool state snapshot."""
    import time as _time
    _ensure_generated()
    out = path or _GENERATED_DIR / "release-state.json"
    summary = registry_summary()
    version = (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    payload = {
        "schema": "release-state.v1",
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "mq_mcp_version": version,
        "tool_count": summary["tool_count"],
        "safety_classes": summary["safety_classes"],
        "categories": summary["categories"],
        "write_capable": summary["write_capable"],
        "subprocess_capable": summary["subprocess_capable"],
        "api_key_required": summary["api_key_required"],
        "source_files": {
            "VERSION": version,
            "tool_contracts": str(_CONTRACTS_PATH.relative_to(_ROOT)),
            "server": str(_SERVER_PATH.relative_to(_ROOT)),
        },
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def export_profile_index(path: Path | None = None) -> Path:
    """Write generated/profile-index.json with all profile metadata."""
    _ensure_generated()
    out = path or _GENERATED_DIR / "profile-index.json"
    profiles_dir = _ROOT / "profiles"
    profiles = []
    for p in sorted(profiles_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            profiles.append({
                "name": data.get("name", p.stem),
                "title": data.get("title", ""),
                "client": data.get("client", ""),
                "summary": data.get("summary", ""),
                "recommended_tools": data.get("recommended_tools", []),
                "safety_notes": data.get("safety_notes", []),
                "source_file": f"profiles/{p.name}",
            })
        except Exception:
            pass
    payload = {
        "schema": "profile-index.v1",
        "generated_from": "profiles/",
        "profile_count": len(profiles),
        "profiles": profiles,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out
