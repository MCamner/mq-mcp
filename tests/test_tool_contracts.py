"""Tests that docs/tool_contracts.json is complete and internally consistent."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "tool_contracts.json"


@pytest.fixture(scope="module")
def contracts():
    return json.loads(CONTRACTS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tools(contracts):
    return contracts["tools"]


# ---------------------------------------------------------------------------
# File-level checks
# ---------------------------------------------------------------------------

def test_contracts_file_exists():
    assert CONTRACTS.exists(), "docs/tool_contracts.json missing"


def test_schema_version(contracts):
    assert contracts.get("schema_version") == "tool-contracts.v1"


def test_tool_count_field_matches_actual(contracts, tools):
    assert contracts["tool_count"] == len(tools), (
        f"tool_count field ({contracts['tool_count']}) != actual tools ({len(tools)})"
    )


def test_no_duplicate_tool_names(tools):
    names = [t["name"] for t in tools]
    seen, dupes = set(), []
    for n in names:
        if n in seen:
            dupes.append(n)
        seen.add(n)
    assert not dupes, f"Duplicate tool names: {dupes}"


# ---------------------------------------------------------------------------
# Per-tool required fields
# ---------------------------------------------------------------------------

def test_every_tool_has_name(tools):
    missing = [t for t in tools if not t.get("name")]
    assert not missing, f"Tools without name: {missing}"


def test_every_tool_has_class(tools):
    missing = [t["name"] for t in tools if not t.get("class")]
    assert not missing, f"Tools without class: {missing}"


def test_every_tool_has_valid_class(tools):
    invalid = [t["name"] for t in tools if t.get("class") not in ("A", "B", "C", "D")]
    assert not invalid, f"Tools with invalid class: {invalid}"


def test_every_tool_has_description(tools):
    missing = [t["name"] for t in tools if not t.get("description", "").strip()]
    assert not missing, f"Tools without description: {missing}"


def test_every_tool_has_resolver(tools):
    missing = [t["name"] for t in tools if "resolver" not in t]
    assert not missing, f"Tools without resolver field: {missing}"


def test_every_tool_has_write_field(tools):
    missing = [t["name"] for t in tools if "write" not in t]
    assert not missing, f"Tools without write field: {missing}"


def test_every_tool_has_subprocess_field(tools):
    missing = [t["name"] for t in tools if "subprocess" not in t]
    assert not missing, f"Tools without subprocess field: {missing}"


def test_every_tool_has_side_effects_field(tools):
    missing = [t["name"] for t in tools if "side_effects" not in t]
    assert not missing, f"Tools without side_effects field: {missing}"


# ---------------------------------------------------------------------------
# Class C/D completeness
# ---------------------------------------------------------------------------

def test_class_cd_have_side_effects(tools):
    violations = [
        t["name"] for t in tools
        if t.get("class") in ("C", "D") and not t.get("side_effects")
    ]
    assert not violations, f"Class C/D tools with empty side_effects: {violations}"


def test_class_c_have_write_true(tools):
    violations = [
        t["name"] for t in tools
        if t.get("class") == "C" and not t.get("write", False)
    ]
    assert not violations, f"Class C tools with write=false: {violations}"


def test_class_d_have_subprocess_true(tools):
    violations = [
        t["name"] for t in tools
        if t.get("class") == "D" and not t.get("subprocess", False)
    ]
    assert not violations, f"Class D tools with subprocess=false: {violations}"


# ---------------------------------------------------------------------------
# New tool detection — incomplete metadata
# ---------------------------------------------------------------------------

def test_no_tool_with_empty_examples_is_acceptable():
    """Examples may be empty (optional field) — just ensure the field exists."""
    tools_data = json.loads(CONTRACTS.read_text(encoding="utf-8"))["tools"]
    missing = [t["name"] for t in tools_data if "examples" not in t]
    assert not missing, f"Tools without examples field: {missing}"
