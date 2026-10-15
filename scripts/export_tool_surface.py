#!/usr/bin/env python3
"""Export contracts/tool_surface.v1.json from the in-process tool registry.

Run from the repository root with mq-mcp's environment:

    uv --directory mq-mcp run python ../scripts/export_tool_surface.py
    uv --directory mq-mcp run python ../scripts/export_tool_surface.py --check

The tool list comes from FastMCP itself, not from grepping server.py, so it is
exactly what a client can call. Classes come from docs/tool_contracts.json
(ADR-003). A registered tool without a class fails the export rather than
publishing "unknown": a consumer must never learn a tool's class by guessing.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contracts" / "tool_surface.v1.json"
CONTRACTS = ROOT / "docs" / "tool_contracts.json"
SCHEMA_ID = "mq-mcp.tool-surface.v1"


def _types(spec: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    declared = spec.get("type")
    if isinstance(declared, str):
        found.add(declared)
    elif isinstance(declared, list):
        found.update(t for t in declared if isinstance(t, str))
    for branch in spec.get("anyOf", []) + spec.get("oneOf", []):
        if isinstance(branch, dict):
            found.update(_types(branch))
    return sorted(found)


def parameters_from_input_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Name, JSON types and required for each parameter, sorted by name."""
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    return [
        {"name": name, "type": _types(spec if isinstance(spec, dict) else {}), "required": name in required}
        for name, spec in sorted(properties.items())
    ]


def signature(parameters: list[dict[str, Any]]) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_surface(registered: list[dict[str, Any]], contracts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tools = []
    for tool in sorted(registered, key=lambda t: t["name"]):
        name = tool["name"]
        declared = contracts.get(name)
        if not declared or declared.get("class") not in {"A", "B", "C", "D"}:
            raise ValueError(f"{name} is registered but has no ADR-003 class in docs/tool_contracts.json")
        parameters = parameters_from_input_schema(tool.get("inputSchema") or {})
        tools.append(
            {
                "name": name,
                "safety_class": declared["class"],
                "write": bool(declared.get("write")),
                "subprocess": bool(declared.get("subprocess")),
                "parameters": parameters,
                "signature_sha256": signature(parameters),
            }
        )
    return {"schema": SCHEMA_ID, "producer": "mq-mcp", "tool_count": len(tools), "tools": tools}


def current_surface() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "mq-mcp"))
    import server  # noqa: PLC0415 — importing registers the tools

    registered = [{"name": t.name, "inputSchema": t.inputSchema} for t in asyncio.run(server.mcp.list_tools())]
    contracts = {t["name"]: t for t in json.loads(CONTRACTS.read_text(encoding="utf-8"))["tools"]}
    return build_surface(registered, contracts)


def render(surface: dict[str, Any]) -> str:
    return json.dumps(surface, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed file is stale; write nothing")
    args = parser.parse_args()

    rendered = render(current_surface())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != rendered:
            print(
                "FAIL: contracts/tool_surface.v1.json is stale — run: "
                "uv --directory mq-mcp run python ../scripts/export_tool_surface.py",
                file=sys.stderr,
            )
            return 1
        print("OK: contracts/tool_surface.v1.json matches the registry")
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
