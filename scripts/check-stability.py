#!/usr/bin/env python3
"""Validate the mq-mcp v1 stability baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABILITY = ROOT / "docs" / "stability.json"
REQUIRED_REQUIREMENTS = {
    "stable_server_startup",
    "stable_tool_registry",
    "stable_tool_metadata_schema",
    "stable_safety_classes",
    "stable_filesystem_boundary_model",
    "stable_config_format",
    "stable_validation_command",
    "stable_install_flow",
    "complete_tool_docs",
    "complete_troubleshooting_docs",
    "complete_example_workflows",
    "green_ci",
    "protected_main_branch",
    "github_release",
    "github_pages_documentation",
    "no_known_critical_safety_gaps",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(path: str) -> None:
    if not (ROOT / path).is_file():
        fail(f"missing required file: {path}")


def main() -> int:
    require_file("VERSION")
    require_file("README.md")
    require_file("CHANGELOG.md")
    require_file("docs/tool_contracts.json")
    require_file("docs/stability.md")
    require_file("docs/stability.json")
    require_file("docs/troubleshooting.md")
    require_file("docs/profiles.md")
    require_file("scripts/validate.sh")
    require_file("scripts/release-check.sh")
    require_file("scripts/check-tool-contracts.sh")
    require_file("scripts/check-profiles.py")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    data = json.loads(STABILITY.read_text(encoding="utf-8"))
    if data.get("schema_version") != "mq-mcp.stability.v1":
        fail("docs/stability.json has wrong schema_version")
    if data.get("version") != version:
        fail(f"stability version {data.get('version')} does not match VERSION {version}")

    contracts = json.loads((ROOT / "docs" / "tool_contracts.json").read_text(encoding="utf-8"))
    if contracts.get("mq_mcp_version") != version:
        fail("tool_contracts.json version does not match VERSION")
    if contracts.get("schema_version") != "tool-contracts.v1":
        fail("tool_contracts.json schema_version is not tool-contracts.v1")

    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        fail("requirements must be a list")

    seen: set[str] = set()
    for item in requirements:
        name = item.get("name")
        if name in seen:
            fail(f"duplicate stability requirement: {name}")
        seen.add(name)
        if item.get("status") != "done":
            fail(f"stability requirement is not done: {name}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(f"stability requirement lacks evidence: {name}")

    missing = REQUIRED_REQUIREMENTS - seen
    if missing:
        fail(f"missing stability requirements: {', '.join(sorted(missing))}")

    print(f"OK: stability baseline validated for v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
