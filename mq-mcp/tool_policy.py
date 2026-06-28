"""Workflow tool policy (Phase 5).

Derives a machine-readable *workflow policy* for every mq-mcp tool from the
existing tool contracts (docs/tool_contracts.json, via tool_registry), plus a
small curated override layer. This lets mq-agent's workflow runner answer,
without a hardcoded allowlist:

  * may this tool run inside a workflow?   -> workflow_allowed
  * what approval level does it need?       -> approval (none|plan|step|forbidden)
  * is it safe to retry / idempotent?       -> retry_safe / idempotent

Policy is *derived*, so every tool automatically has one and the set can never
drift out of sync with the tool catalog. Overrides are sparse and validated to
reference real tools.

approval levels:
  none       read-only, no subprocess, no external side effects
  plan       read-only subprocess / test run (whole plan approved once)
  step       file write / network / external mutation (approve each step)
  forbidden  arbitrary execution, push/release, recursive workflow start
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import tool_registry

POLICY_SCHEMA = "tool-policy.v1"

APPROVAL_NONE = "none"
APPROVAL_PLAN = "plan"
APPROVAL_STEP = "step"
APPROVAL_FORBIDDEN = "forbidden"
_APPROVAL_VALUES = frozenset(
    {APPROVAL_NONE, APPROVAL_PLAN, APPROVAL_STEP, APPROVAL_FORBIDDEN}
)

#: Tools that may never run inside a workflow regardless of derivation:
#: arbitrary local execution and the unbounded mqlaunch entrypoints (which can
#: push, release, or recursively start another workflow).
FORBIDDEN_TOOLS: frozenset[str] = frozenset(
    {
        "shell_exec",
        "run_mqlaunch",  # generic passthrough — can run any mqlaunch subcommand
        "run_mqlaunch_ask",  # interactive / free-form
        "run_mqlaunch_bundle",  # produces release bundles
        "run_mqlaunch_demo",  # interactive demo
    }
)

#: Categories whose tools drive the desktop / TUI and produce output unsuited to
#: unattended workflow steps (open apps, screenshots, clipboard, wallpaper, …).
_NON_WORKFLOW_CATEGORIES: frozenset[str] = frozenset({"macos"})

#: Sparse explicit overrides. Every key MUST be a real tool (validated).
OVERRIDES: dict[str, dict[str, Any]] = {}


def _derive_approval(entry: dict[str, Any]) -> str:
    name = entry["name"]
    if name in FORBIDDEN_TOOLS:
        return APPROVAL_FORBIDDEN
    # STEP (per-step approval) is reserved for genuine mutation. A non-writing
    # network call (e.g. an OpenAI review) is billable but read-only, so it is
    # PLAN, not STEP — otherwise it conflates with file writes and the read-only
    # workflow runner refuses it (it treats STEP as mutation), which blocked the
    # whole review/risk tool family from any read-only workflow.
    if entry["writes_files"]:
        return APPROVAL_STEP
    if entry["uses_network"]:
        return APPROVAL_PLAN  # read-only external call — plan-level approval
    if entry["uses_subprocess"]:
        return APPROVAL_PLAN  # read-only subprocess / test run
    return APPROVAL_NONE


def policy_for(entry: dict[str, Any]) -> dict[str, Any]:
    """Build the workflow policy for one normalized registry entry."""
    name = entry["name"]
    write = bool(entry["writes_files"])
    approval = _derive_approval(entry)
    is_tui = entry["category"] in _NON_WORKFLOW_CATEGORIES

    workflow_allowed = approval != APPROVAL_FORBIDDEN and not is_tui
    idempotent = not write
    retry_safe = (not write) and approval in (APPROVAL_NONE, APPROVAL_PLAN)

    policy = {
        "name": name,
        "class": entry["safety_class"],
        "write": write,
        "subprocess": bool(entry["uses_subprocess"]),
        "network": bool(entry["uses_network"]),
        "side_effects": list(entry["side_effects"]),
        "approval": approval,
        "workflow_allowed": workflow_allowed,
        "idempotent": idempotent,
        "retry_safe": retry_safe,
    }
    policy.update(OVERRIDES.get(name, {}))
    return policy


def all_policies() -> list[dict[str, Any]]:
    """Return the workflow policy for every tool, sorted by name."""
    return sorted(
        (policy_for(e) for e in tool_registry.load_registry()),
        key=lambda p: p["name"],
    )


def get_policy(name: str) -> dict[str, Any] | None:
    """Return one tool's policy, or ``None`` if the tool is unknown."""
    for entry in tool_registry.load_registry():
        if entry["name"] == name:
            return policy_for(entry)
    return None


def validate_policies() -> list[str]:
    """Return a list of policy problems (empty list == healthy).

    Catches tools without a usable policy and overrides / forbidden entries that
    reference a tool which does not exist in the catalog.
    """
    names = {e["name"] for e in tool_registry.load_registry()}
    problems: list[str] = []

    for name in sorted(names):
        policy = get_policy(name)
        if policy is None:
            problems.append(f"tool without policy: {name}")
            continue
        if policy["approval"] not in _APPROVAL_VALUES:
            problems.append(f"{name}: invalid approval {policy['approval']!r}")
        if policy["approval"] == APPROVAL_FORBIDDEN and policy["workflow_allowed"]:
            problems.append(f"{name}: forbidden tool marked workflow_allowed")

    for override_name in OVERRIDES:
        if override_name not in names:
            problems.append(f"policy override for unknown tool: {override_name}")
    for forbidden_name in FORBIDDEN_TOOLS:
        if forbidden_name not in names:
            problems.append(f"forbidden list references unknown tool: {forbidden_name}")

    return problems


def export_tool_policies(path: Path | None = None) -> Path:
    """Write generated/tool-policies.json and return the path."""
    import json

    root = Path(__file__).resolve().parents[1]
    out = path or (root / "generated" / "tool-policies.json")
    out.parent.mkdir(exist_ok=True)
    policies = all_policies()
    payload = {
        "schema": POLICY_SCHEMA,
        "generated_from": "docs/tool_contracts.json",
        "tool_count": len(policies),
        "workflow_allowed_count": sum(1 for p in policies if p["workflow_allowed"]),
        "tools": policies,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out
