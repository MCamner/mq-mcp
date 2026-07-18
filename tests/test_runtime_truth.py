"""Tests that public version signals agree with each other and with runtime."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
VERSION_FILE = ROOT / "VERSION"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
STABILITY = ROOT / "docs" / "stability.json"
TOOL_SAFETY = ROOT / "docs" / "TOOL_SAFETY.md"
CONTRACTS = ROOT / "docs" / "tool_contracts.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runtime_tool_names() -> list[str]:
    src = SERVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)

    def is_mcp_tool(node):
        if isinstance(node, ast.Call):
            node = node.func
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "tool"
            and isinstance(node.value, ast.Name)
            and node.value.id == "mcp"
        )

    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(is_mcp_tool(d) for d in node.decorator_list):
                names.append(node.name)
    return sorted(names)


def _current_version() -> str:
    return VERSION_FILE.read_text().strip()


# ---------------------------------------------------------------------------
# VERSION
# ---------------------------------------------------------------------------

def test_version_file_exists():
    assert VERSION_FILE.exists(), "VERSION file missing"


def test_version_is_semver():
    version = _current_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"VERSION '{version}' is not semver-compatible (expected X.Y.Z)"
    )


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

def test_readme_badge_matches_version():
    version = _current_version()
    readme = README.read_text()
    assert f"version-{version}-" in readme, (
        f"README badge does not contain version-{version}-"
    )


def test_readme_release_link_matches_version():
    version = _current_version()
    readme = README.read_text()
    assert f"releases/tag/v{version}" in readme, (
        f"README release link does not contain releases/tag/v{version}"
    )


def test_readme_tool_count_matches_runtime():
    runtime_count = len(_runtime_tool_names())
    readme = README.read_text()
    m = re.search(r"\b(\d+)\s+(?:documented[^\n]*)tools", readme)
    assert m is not None, "Could not find tool count in README"
    readme_count = int(m.group(1))
    assert readme_count == runtime_count, (
        f"README tool count ({readme_count}) does not match runtime ({runtime_count})"
    )


# ---------------------------------------------------------------------------
# CHANGELOG
# ---------------------------------------------------------------------------

def test_changelog_has_current_version():
    version = _current_version()
    changelog = CHANGELOG.read_text()
    assert re.search(rf"^## (?:\[)?{re.escape(version)}(?:\])?", changelog, re.MULTILINE), (
        f"CHANGELOG missing entry for version {version}"
    )


# ---------------------------------------------------------------------------
# docs/stability.json
# ---------------------------------------------------------------------------

def test_stability_json_version_matches():
    version = _current_version()
    assert STABILITY.exists(), "docs/stability.json missing"
    data = json.loads(STABILITY.read_text())
    assert data.get("version") == version, (
        f"docs/stability.json version '{data.get('version')}' does not match VERSION '{version}'"
    )


# ---------------------------------------------------------------------------
# TOOL_SAFETY.md coverage
# ---------------------------------------------------------------------------

def test_all_runtime_tools_in_tool_safety():
    tools = _runtime_tool_names()
    safety_text = TOOL_SAFETY.read_text()
    missing = [t for t in tools if t not in safety_text]
    assert not missing, (
        f"Tools missing from docs/TOOL_SAFETY.md: {missing}"
    )


def test_no_phantom_tools_in_tool_safety():
    runtime_tools = set(_runtime_tool_names())
    safety_text = TOOL_SAFETY.read_text()
    # Only match tool names in table rows (lines starting with `| `tool_name``)
    documented = set(re.findall(r"^\|\s+`([a-z][a-z_]+)`", safety_text, re.MULTILINE))
    phantom = documented - runtime_tools
    assert not phantom, (
        f"Tools in docs/TOOL_SAFETY.md not found in runtime: {phantom}"
    )


# ---------------------------------------------------------------------------
# Class C/D metadata
# ---------------------------------------------------------------------------

def test_class_cd_tools_have_metadata():
    assert CONTRACTS.exists(), "docs/tool_contracts.json missing"
    data = json.loads(CONTRACTS.read_text())
    gaps = []
    for t in data["tools"]:
        cls = t.get("safety_class") or t.get("class", "")
        if cls not in ("C", "D"):
            continue
        missing_fields = []
        if not t.get("name"):
            missing_fields.append("name")
        if not t.get("description"):
            missing_fields.append("description")
        if "write" not in t and "writes_files" not in t:
            missing_fields.append("write/writes_files")
        if missing_fields:
            gaps.append(f"{t.get('name', '?')}: {missing_fields}")
    assert not gaps, f"Class C/D tools missing metadata: {gaps}"


# ---------------------------------------------------------------------------
# check-runtime-truth.sh integration
# ---------------------------------------------------------------------------

def test_check_runtime_truth_script_passes():
    script = ROOT / "scripts" / "check-runtime-truth.sh"
    assert script.exists(), "scripts/check-runtime-truth.sh missing"
    result = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        f"check-runtime-truth.sh failed:\n{result.stdout}\n{result.stderr}"
    )
