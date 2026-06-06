"""Deterministic Release Gate v2 checks."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .models import GateCheck


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def check_tests_pass(repo: Path, test_command: list[str] | None = None) -> GateCheck:
    if not test_command:
        return GateCheck(
            name="tests_pass",
            status="warning",
            message="Tests were not run for this gate invocation.",
            next_action="Run Release Gate v2 with a test command before release.",
        )
    try:
        result = subprocess.run(
            test_command,
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        return GateCheck(
            name="tests_pass",
            status="blocked",
            message=f"Test command failed to run: {exc}",
            blocker=True,
            next_action="Fix the test command and rerun tests.",
        )
    if result.returncode == 0:
        return GateCheck("tests_pass", "pass", "Tests passed.")
    return GateCheck(
        name="tests_pass",
        status="blocked",
        message="Tests failed.",
        blocker=True,
        next_action="Fix failing tests and rerun Release Gate v2.",
    )


def check_version_consistent(repo: Path, target: str) -> GateCheck:
    version = target.removeprefix("v")
    version_file = repo / "VERSION"
    pyproject = repo / "pyproject.toml"
    values: list[str] = []
    if version_file.is_file():
        values.append(version_file.read_text(encoding="utf-8").strip().removeprefix("v"))
    if pyproject.is_file():
        text = _read(pyproject)
        if f'version = "{version}"' in text or f"version = '{version}'" in text:
            values.append(version)
    if not values:
        return GateCheck(
            "version_consistent",
            "blocked",
            f"No VERSION or pyproject version found for {target}.",
            blocker=True,
            next_action="Add or sync release version metadata.",
        )
    if all(value == version for value in values):
        return GateCheck("version_consistent", "pass", f"Version metadata matches {target}.")
    return GateCheck(
        "version_consistent",
        "blocked",
        f"Version metadata does not match {target}.",
        blocker=True,
        next_action="Sync VERSION and pyproject.toml with the target version.",
    )


def check_file_mentions_target(repo: Path, filename: str, target: str, blocker: bool) -> GateCheck:
    path = repo / filename
    name = filename.lower().replace(".", "_")
    if not path.is_file():
        return GateCheck(
            name=name,
            status="blocked" if blocker else "warning",
            message=f"{filename} is missing.",
            blocker=blocker,
            next_action=f"Add {filename} before release.",
        )
    text = _read(path)
    if target in text or target.removeprefix("v") in text:
        return GateCheck(name, "pass", f"{filename} mentions {target}.")
    return GateCheck(
        name=name,
        status="blocked" if blocker else "warning",
        message=f"{filename} does not mention {target}.",
        blocker=blocker,
        next_action=f"Update {filename} for {target}.",
    )


def check_contracts_valid(repo: Path) -> GateCheck:
    candidates = [repo / "docs" / "tool_contracts.json", repo / "contracts" / "release_gate_v2.schema.json"]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return GateCheck(
            "contracts_valid",
            "blocked",
            "No release/tool contract schema was found.",
            blocker=True,
            next_action="Add docs/tool_contracts.json or contracts/release_gate_v2.schema.json.",
        )
    for path in existing:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return GateCheck(
                "contracts_valid",
                "blocked",
                f"Invalid JSON contract: {path.relative_to(repo)} ({exc})",
                blocker=True,
                next_action="Fix invalid contract JSON.",
            )
    return GateCheck("contracts_valid", "pass", "Contract JSON files are valid.")


def check_safety_classes_valid(repo: Path) -> GateCheck:
    path = repo / "docs" / "tool_contracts.json"
    if not path.is_file():
        return GateCheck(
            "safety_classes_valid",
            "warning",
            "docs/tool_contracts.json is not present; no tool safety classes checked.",
            next_action="Add tool safety contract metadata if this repo exposes tools.",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return GateCheck("safety_classes_valid", "blocked", f"Cannot parse tool contracts: {exc}", True, "Fix tool_contracts.json.")
    tools = data.get("tools", [])
    missing = [str(tool.get("name", "<unnamed>")) for tool in tools if not (tool.get("class") or tool.get("safety_class"))]
    if missing:
        return GateCheck(
            "safety_classes_valid",
            "blocked",
            f"Tools missing safety class: {', '.join(missing[:5])}",
            blocker=True,
            next_action="Add safety class metadata for every tool.",
        )
    return GateCheck("safety_classes_valid", "pass", "Tool safety classes are present.")


def check_release_notes_present(repo: Path, target: str) -> GateCheck:
    release_notes = repo / "docs" / "RELEASE_NOTES.md"
    changelog = repo / "CHANGELOG.md"
    version = target.removeprefix("v")
    release_text = _read(release_notes)
    changelog_text = _read(changelog)
    if (
        release_notes.is_file()
        and (target in release_text or version in release_text)
    ) or (
        changelog.is_file()
        and (target in changelog_text or version in changelog_text)
    ):
        return GateCheck("release_notes_present", "pass", f"Release notes mention {target}.")
    return GateCheck(
        "release_notes_present",
        "blocked",
        f"Release notes for {target} are missing.",
        blocker=True,
        next_action="Add release notes or a CHANGELOG entry for the target.",
    )


def run_p0_checks(repo: Path, target: str, test_command: list[str] | None = None) -> list[GateCheck]:
    return [
        check_tests_pass(repo, test_command),
        check_version_consistent(repo, target),
        check_file_mentions_target(repo, "CHANGELOG.md", target, blocker=True),
        check_file_mentions_target(repo, "README.md", target, blocker=False),
        check_file_mentions_target(repo, "ROADMAP.md", target, blocker=False),
        check_contracts_valid(repo),
        check_safety_classes_valid(repo),
        check_release_notes_present(repo, target),
    ]
