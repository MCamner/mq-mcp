#!/usr/bin/env python3
"""Validate mq-mcp profile templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "profiles"
REQUIRED_FIELDS = {
    "schema_version",
    "name",
    "title",
    "summary",
    "client",
    "command",
    "args",
    "env",
    "recommended_tools",
    "safety_notes",
}
EXPECTED_PROFILES = {
    "claude-desktop",
    "codex",
    "developer",
    "local-macos",
    "mq-agent",
    "openai-bridge",
    "read-only",
    "repo-only",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if not PROFILES_DIR.is_dir():
        fail("profiles directory is missing")

    paths = sorted(PROFILES_DIR.glob("*.json"))
    names: set[str] = set()

    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"{path}: invalid JSON: {exc}")

        missing = REQUIRED_FIELDS - set(data)
        if missing:
            fail(f"{path}: missing fields: {', '.join(sorted(missing))}")

        if data["schema_version"] != "mq-mcp.profile.v1":
            fail(f"{path}: unsupported schema_version {data['schema_version']!r}")

        name = data["name"]
        if path.stem != name:
            fail(f"{path}: filename must match name {name!r}")
        if name in names:
            fail(f"{path}: duplicate profile name {name!r}")
        names.add(name)

        if not isinstance(data["args"], list) or not data["args"]:
            fail(f"{path}: args must be a non-empty list")
        if not isinstance(data["env"], dict):
            fail(f"{path}: env must be an object")
        if not isinstance(data["recommended_tools"], list) or not data["recommended_tools"]:
            fail(f"{path}: recommended_tools must be a non-empty list")
        if not isinstance(data["safety_notes"], list) or not data["safety_notes"]:
            fail(f"{path}: safety_notes must be a non-empty list")

    missing_profiles = EXPECTED_PROFILES - names
    if missing_profiles:
        fail(f"missing expected profiles: {', '.join(sorted(missing_profiles))}")

    print(f"OK: validated {len(paths)} profile templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
