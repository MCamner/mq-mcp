"""Workflow tool-policy tests (Phase 5).

Verifies every mq-mcp tool has a valid, derivable workflow policy and that the
curated overrides / forbidden list reference only real tools — this is the CI
guard the roadmap asks for ("CI should find tools without policy" and "policy
for tools that don't exist").
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mq-mcp"))

import tool_policy  # noqa: E402
import tool_registry  # noqa: E402


def test_every_tool_has_a_valid_policy():
    assert tool_policy.validate_policies() == []


def test_all_policies_cover_the_whole_catalog():
    policies = tool_policy.all_policies()
    names = {e["name"] for e in tool_registry.load_registry()}
    assert {p["name"] for p in policies} == names
    assert len(policies) == len(names)


def test_policy_has_all_required_fields():
    policy = tool_policy.get_policy("run_mqlaunch_selftest")
    assert set(policy) == {
        "name", "class", "write", "subprocess", "network",
        "side_effects", "approval", "workflow_allowed", "idempotent", "retry_safe",
    }


@pytest.mark.parametrize("name", ["shell_exec", "run_mqlaunch"])
def test_forbidden_tools_are_not_workflow_allowed(name):
    policy = tool_policy.get_policy(name)
    assert policy["approval"] == tool_policy.APPROVAL_FORBIDDEN
    assert policy["workflow_allowed"] is False
    assert policy["retry_safe"] is False


@pytest.mark.parametrize(
    "name",
    ["run_mqlaunch_doctor", "run_mqlaunch_selftest", "run_mqlaunch_release_check"],
)
def test_readonly_mqlaunch_tools_are_plan_and_allowed(name):
    policy = tool_policy.get_policy(name)
    assert policy["approval"] == tool_policy.APPROVAL_PLAN
    assert policy["workflow_allowed"] is True
    assert policy["retry_safe"] is True
    assert policy["write"] is False


def test_macos_tools_are_not_workflow_allowed():
    # Desktop/TUI tools produce output unsuited to unattended workflow steps.
    for name in ("open_chrome", "take_screenshot", "set_wallpaper"):
        policy = tool_policy.get_policy(name)
        if policy is not None:  # tool may not exist in every build
            assert policy["workflow_allowed"] is False, name


def test_write_tool_requires_step_and_is_not_retry_safe():
    policy = tool_policy.get_policy("update_repo_file")
    assert policy["write"] is True
    assert policy["approval"] == tool_policy.APPROVAL_STEP
    assert policy["idempotent"] is False
    assert policy["retry_safe"] is False


@pytest.mark.parametrize("name", ["review_diff", "review_file", "review_repo"])
def test_readonly_network_review_tools_are_plan_not_step(name):
    # A non-writing network (OpenAI) call is billable but read-only, so it is
    # PLAN — never STEP. STEP is reserved for mutation; treating network as STEP
    # made the read-only workflow runner reject the whole review tool family.
    policy = tool_policy.get_policy(name)
    assert policy["write"] is False
    assert policy["network"] is True
    assert policy["approval"] == tool_policy.APPROVAL_PLAN
    assert policy["workflow_allowed"] is True


def test_step_approval_is_reserved_for_writes():
    # No read-only (non-writing) tool may carry STEP approval — otherwise the
    # read-only runner would refuse it as if it were a mutation.
    offenders = [
        p["name"]
        for p in tool_policy.all_policies()
        if p["approval"] == tool_policy.APPROVAL_STEP and not p["write"]
    ]
    assert offenders == [], f"read-only tools wrongly marked STEP: {offenders}"


def test_read_only_no_subprocess_is_approval_none():
    policy = tool_policy.get_policy("repo_signal_status")
    assert policy["approval"] == tool_policy.APPROVAL_NONE
    assert policy["workflow_allowed"] is True


def test_get_policy_unknown_returns_none():
    assert tool_policy.get_policy("no_such_tool_xyz") is None


def test_validate_flags_override_for_unknown_tool(monkeypatch):
    monkeypatch.setattr(tool_policy, "OVERRIDES", {"ghost_tool": {"approval": "none"}})
    problems = tool_policy.validate_policies()
    assert any("ghost_tool" in p for p in problems)


def test_export_writes_valid_schema(tmp_path):
    out = tool_policy.export_tool_policies(tmp_path / "tool-policies.json")
    import json

    data = json.loads(out.read_text())
    assert data["schema"] == tool_policy.POLICY_SCHEMA
    assert data["tool_count"] == len(data["tools"])
    assert data["workflow_allowed_count"] <= data["tool_count"]
