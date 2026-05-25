#!/usr/bin/env python3
"""Generate docs/tool_contracts.json from server.py + static metadata.

Run from the repository root:
    python scripts/generate_tool_contracts.py
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mq-mcp" / "server.py"
OUT = ROOT / "docs" / "tool_contracts.json"

# Static metadata that cannot be derived from server.py type annotations.
# class: A=read-only repo, B=read-only external, C=write, D=subprocess/app
# resolver: which path resolver the tool uses (or "none")
# write: does the tool modify files on disk
# subprocess: does the tool spawn external processes
# side_effects: observable effects beyond the return value
TOOL_META: dict[str, dict] = {
    "analyze_csv":            {"class": "A", "resolver": "resolve_repo_file",           "write": False, "subprocess": False, "side_effects": []},
    "git_diff":               {"class": "A", "resolver": "run_repo_command",             "write": False, "subprocess": True,  "side_effects": []},
    "git_status":             {"class": "A", "resolver": "run_repo_command",             "write": False, "subprocess": True,  "side_effects": []},
    "list_local_repos":       {"class": "A", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": []},
    "list_openable_apps":     {"class": "A", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": []},
    "list_repo_files":        {"class": "A", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": []},
    "read_repo_file":         {"class": "A", "resolver": "resolve_repo_file",           "write": False, "subprocess": False, "side_effects": []},
    "search_repo":            {"class": "A", "resolver": "run_repo_command",             "write": False, "subprocess": True,  "side_effects": []},
    "tool_safety_report":     {"class": "A", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": []},

    "analyze_guitar_pro":     {"class": "B", "resolver": "resolve_allowed_local_file",  "write": False, "subprocess": False, "side_effects": []},
    "check_port":             {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "find_large_files":       {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "find_recent_files":      {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "get_battery_status":     {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "get_clipboard":          {"class": "B", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": ["clipboard-read"]},
    "get_public_ip":          {"class": "B", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": ["network"]},
    "get_system_resources":   {"class": "B", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": []},
    "get_todays_events":      {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "get_wifi_info":          {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "list_running_apps":      {"class": "B", "resolver": "none",                         "write": False, "subprocess": True,  "side_effects": []},
    "repo_signal_analyze":    {"class": "B", "resolver": "resolve_allowed_local_file",  "write": False, "subprocess": True,  "side_effects": []},
    "repo_signal_checklist":  {"class": "B", "resolver": "resolve_allowed_local_file",  "write": False, "subprocess": True,  "side_effects": []},
    "repo_signal_doctor_json":{"class": "B", "resolver": "resolve_allowed_local_file",  "write": False, "subprocess": True,  "side_effects": []},
    "repo_signal_inspect":    {"class": "B", "resolver": "resolve_allowed_local_file",  "write": False, "subprocess": True,  "side_effects": []},

    "edit_image":             {"class": "C", "resolver": "resolve_allowed_local_file",  "write": True,  "subprocess": False, "side_effects": ["file-write"]},
    "set_clipboard":          {"class": "C", "resolver": "none",                         "write": False, "subprocess": False, "side_effects": ["clipboard-write"]},
    "take_screenshot":        {"class": "C", "resolver": "none",                         "write": True,  "subprocess": True,  "side_effects": ["file-write", "screen"]},
    "update_repo_file":       {"class": "C", "resolver": "resolve_repo_file",           "write": True,  "subprocess": False, "side_effects": ["file-write"]},

    "create_note":            {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "hal_repo_report":        {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": []},
    "lock_screen":            {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["system"]},
    "open_app":               {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_chrome":            {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_finder":            {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_in_app":            {"class": "D", "resolver": "resolve_allowed_local_file",  "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_messages":          {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_repo_terminal":     {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_spotify":           {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_terminal":          {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_url":               {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "open_vscode":            {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "run_mqlaunch":           {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch", "subprocess"]},
    "run_tests":              {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["subprocess"]},
    "set_reminder":           {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["app-launch"]},
    "set_volume":             {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["system", "audio"]},
    "set_wallpaper":          {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["system"]},
    "show_notification":      {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["notification"]},
    "speak_text":             {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["audio"]},
    "toggle_dark_mode":       {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["system"]},
    "validate_project":       {"class": "D", "resolver": "none", "write": False, "subprocess": True,  "side_effects": ["subprocess"]},
}


def extract_tools(source: str) -> dict[str, str]:
    """Extract {name: first_docstring_line} for every @mcp.tool() function."""
    tree = ast.parse(source)
    tools: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        decorated = any(
            (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool")
            or (isinstance(d, ast.Attribute) and d.attr == "tool")
            for d in node.decorator_list
        )
        if not decorated:
            continue
        doc = ast.get_docstring(node) or ""
        first_line = doc.splitlines()[0].strip() if doc else ""
        tools[node.name] = first_line
    return tools


def main() -> int:
    source = SERVER.read_text(encoding="utf-8")
    server_tools = extract_tools(source)

    missing_meta = sorted(set(server_tools) - set(TOOL_META))
    extra_meta = sorted(set(TOOL_META) - set(server_tools))

    if missing_meta:
        print(f"ERROR: tools in server.py with no metadata entry: {missing_meta}", file=sys.stderr)
    if extra_meta:
        print(f"WARNING: metadata entries with no matching server.py tool: {extra_meta}", file=sys.stderr)
    if missing_meta:
        return 1

    tools = []
    for name in sorted(server_tools):
        meta = TOOL_META[name]
        tools.append({
            "name": name,
            "class": meta["class"],
            "description": server_tools[name],
            "resolver": meta["resolver"],
            "write": meta["write"],
            "subprocess": meta["subprocess"],
            "side_effects": meta["side_effects"],
            "examples": [],
        })

    contract = {
        "schema_version": "tool-contracts.v1",
        "mq_mcp_version": (ROOT / "VERSION").read_text().strip(),
        "tool_count": len(tools),
        "tools": tools,
    }

    OUT.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: wrote {len(tools)} tool contracts to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
