"""Enforce safety class rules against docs/tool_contracts.json.

Each safety class has hard invariants:
  A — read-only, no file writes, no arbitrary subprocess
  B — read-only, no file writes
  C — controlled write, must document side effects, must not auto-commit
  D — subprocess/system-effect, must document side effects
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "tool_contracts.json"


@pytest.fixture(scope="module")
def tools():
    return json.loads(CONTRACTS.read_text(encoding="utf-8"))["tools"]


def _by_class(tools, cls):
    return [t for t in tools if t.get("class") == cls]


# ---------------------------------------------------------------------------
# Class A — repo-scoped read-only
# ---------------------------------------------------------------------------

def test_class_a_no_file_writes(tools):
    violations = [
        t["name"] for t in _by_class(tools, "A") if t.get("write", False)
    ]
    assert not violations, f"Class A tools that write files: {violations}"


def test_class_a_no_arbitrary_subprocess(tools):
    """Class A may use subprocess only via the run_repo_command resolver (safe git reads)."""
    violations = [
        t["name"] for t in _by_class(tools, "A")
        if t.get("subprocess", False) and t.get("resolver") != "run_repo_command"
    ]
    assert not violations, (
        f"Class A tools with subprocess outside git boundary: {violations}"
    )


def test_class_a_tools_have_repo_or_safe_resolver(tools):
    """Class A resolvers must be one of the known safe options."""
    safe_resolvers = {"resolve_repo_file", "run_repo_command", "none"}
    violations = [
        t["name"] for t in _by_class(tools, "A")
        if t.get("resolver") not in safe_resolvers
    ]
    assert not violations, f"Class A tools with unexpected resolver: {violations}"


# ---------------------------------------------------------------------------
# Class B — external/system read-only
# ---------------------------------------------------------------------------

def test_class_b_no_file_writes(tools):
    violations = [
        t["name"] for t in _by_class(tools, "B") if t.get("write", False)
    ]
    assert not violations, f"Class B tools that write files: {violations}"


# ---------------------------------------------------------------------------
# Class C — controlled write
# ---------------------------------------------------------------------------

def test_class_c_writes_files(tools):
    violations = [
        t["name"] for t in _by_class(tools, "C") if not t.get("write", False)
    ]
    assert not violations, f"Class C tools that don't write: {violations}"


def test_class_c_documents_side_effects(tools):
    violations = [
        t["name"] for t in _by_class(tools, "C") if not t.get("side_effects")
    ]
    assert not violations, f"Class C tools with no side_effects: {violations}"


def test_class_c_no_auto_commit(tools):
    """Class C tools must not have git-commit in their side effects."""
    violations = [
        t["name"] for t in _by_class(tools, "C")
        if "git-commit" in t.get("side_effects", [])
    ]
    assert not violations, f"Class C tools that auto-commit: {violations}"


def test_class_c_descriptions_mention_write_scope(tools):
    """Class C descriptions must be non-empty (can't have a silent write)."""
    violations = [
        t["name"] for t in _by_class(tools, "C")
        if not t.get("description", "").strip()
    ]
    assert not violations, f"Class C tools with no description: {violations}"


# ---------------------------------------------------------------------------
# Class D — subprocess/open-app/system effect
# ---------------------------------------------------------------------------

def test_class_d_uses_subprocess(tools):
    violations = [
        t["name"] for t in _by_class(tools, "D") if not t.get("subprocess", False)
    ]
    assert not violations, f"Class D tools without subprocess=true: {violations}"


def test_class_d_documents_side_effects(tools):
    violations = [
        t["name"] for t in _by_class(tools, "D") if not t.get("side_effects")
    ]
    assert not violations, f"Class D tools with no side_effects: {violations}"


def test_class_d_descriptions_non_empty(tools):
    violations = [
        t["name"] for t in _by_class(tools, "D")
        if not t.get("description", "").strip()
    ]
    assert not violations, f"Class D tools with no description: {violations}"


# ---------------------------------------------------------------------------
# Cross-class invariants
# ---------------------------------------------------------------------------

def test_no_tool_auto_commits(tools):
    """No tool of any class should auto-commit."""
    auto_committers = [
        t["name"] for t in tools
        if "git-commit" in t.get("side_effects", [])
    ]
    assert not auto_committers, f"Tools that auto-commit: {auto_committers}"


def test_all_classes_present(tools):
    """The registry must contain tools from all four safety classes."""
    classes = {t.get("class") for t in tools}
    for cls in ("A", "B", "C", "D"):
        assert cls in classes, f"No tools found with safety class {cls}"


# ---------------------------------------------------------------------------
# check-tool-contracts.sh integration
# ---------------------------------------------------------------------------

def test_check_tool_contracts_script_passes():
    script = ROOT / "scripts" / "check-tool-contracts.sh"
    assert script.exists(), "scripts/check-tool-contracts.sh missing"
    result = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        f"check-tool-contracts.sh failed:\n{result.stdout}\n{result.stderr}"
    )
