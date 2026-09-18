#!/usr/bin/env python3
"""Check that MCP CI assertions and the read-only release gate cannot drift silently."""
from __future__ import annotations

import re
import sys
import tempfile
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# These workflows or steps cannot be run by the read-only local preflight.
CI_ONLY = {
    "markdownlint.yml": "CI-only: Node markdownlint action; READY does not attest Markdown style.",
    "release.yml": "CI-only: publishing a release requires a pushed version tag.",
}
CI_ONLY_STEPS = {
    "Run local validation": "CI-only: validate.sh runs registry export, which writes gitignored artifacts.",
    "Verify tool_contracts.json is up to date": "CI-only: generation rewrites docs/tool_contracts.json before comparing it.",
}
STEPS = {
    "docs-consistency.yml": [
        "Skills are consistent (frontmatter, cross-refs, paths, SKILLS.md)",
        "Python version in install.md is not 3.14",
        "No stale tool counts (13 tools, 14 tools)",
        "VERSION matches pyproject.toml", "VERSION matches .mq/repo-contract.json",
        "README references current version", "CHANGELOG references current version",
    ],
    "validate.yml": [
        "Checkout", "Set up uv", "Set up Python", "Install dependencies",
        "Validate shell script syntax", "Compile Python files", "Run local validation",
        "Check tool contracts", "Check profiles", "Check stability baseline",
        "Verify tool_contracts.json is up to date", "Run tests",
    ],
    "gate-parity.yml": [
        "Checkout", "Set up uv", "Set up Python", "Install dependencies",
        "Validate gate parity", "Test parity failures", "Run release preflight",
    ],
}
CI_COMMANDS = {
    "docs-consistency.yml": [
        "./scripts/check-skills.sh", "docs/install.md", "13 tools",
        "mq-mcp/pyproject.toml", ".mq/repo-contract.json", "README.md", "CHANGELOG.md",
    ],
    "validate.yml": [
        "bash -n scripts/validate.sh", "./scripts/validate.sh",
        "./scripts/check-tool-contracts.sh", "./scripts/check-profiles.py",
        "./scripts/check-stability.py", "python3 scripts/generate_tool_contracts.py",
        "uv --directory mq-mcp run pytest ../tests/ -v",
    ],
    "gate-parity.yml": [
        "python3 scripts/check-gate-parity.py", "--self-test", "./release-check.sh --json",
    ],
}
LOCAL_COMMANDS = {
    "skills": 'run "skills" bash scripts/check-skills.sh',
    "profiles": 'run "profiles" "$PYTHON_BIN" scripts/check-profiles.py',
    "stability": 'run "stability" "$PYTHON_BIN" scripts/check-stability.py',
    "syntax": 'run "validate.sh syntax" bash -n scripts/validate.sh',
    "tests": 'run "pytest" uv --directory mq-mcp run --no-sync pytest ../tests/ -q',
    "parity": 'run "check-gate-parity.py" "$PYTHON_BIN" scripts/check-gate-parity.py',
    "contracts": 'run "tool contracts (entries + safety classes)" bash scripts/check-tool-contracts.sh',
}


def verify(root: Path, *, check_docs: bool = True) -> list[str]:
    errors: list[str] = []
    workflow_dir = root / ".github" / "workflows"
    found = {p.name for ext in ("*.yml", "*.yaml") for p in workflow_dir.glob(ext)}
    expected = set(STEPS) | set(CI_ONLY)
    for name in sorted(found - expected):
        errors.append(f"undeclared workflow: {name}")
    for name in sorted(expected - found):
        errors.append(f"declared workflow absent: {name}")
    for name, reason in {**CI_ONLY, **CI_ONLY_STEPS}.items():
        if not reason.startswith("CI-only:") or len(reason) < 30:
            errors.append(f"missing CI-only rationale: {name}")
    for name, step_names in STEPS.items():
        path = workflow_dir / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        actual = re.findall(r"^\s*- name:\s*(.+?)\s*$", text, re.M)
        if Counter(actual) != Counter(step_names):
            errors.append(f"workflow steps changed: {name}: {actual!r}")
        for command in CI_COMMANDS[name]:
            if command not in text:
                errors.append(f"CI command missing in {name}: {command}")
    gate = root / "release-check.sh"
    if not gate.is_file():
        errors.append("release-check.sh absent")
    else:
        text = gate.read_text(encoding="utf-8")
        for label, command in LOCAL_COMMANDS.items():
            if command not in text:
                errors.append(f"local gate missing {label}: {command}")
        # Check executable lines rather than comments, which document exceptions.
        executable = "\n".join(line for line in text.splitlines()
                               if not line.lstrip().startswith("#"))
        if re.search(r"\b(?:bash\s+)?scripts/validate\.sh\b|generate_tool_contracts\.py", executable):
            errors.append("write-capable CI generator invoked from read-only gate")
    if not check_docs:
        return errors
    version_path = root / "VERSION"
    project_path = root / "mq-mcp" / "pyproject.toml"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
        project_version = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]["version"]
        if project_version != version:
            errors.append(f"VERSION differs from pyproject.toml: {project_version}")
    except (OSError, ValueError, KeyError) as exc:
        errors.append(f"cannot validate Python version surface: {exc}")
    install = root / "docs" / "install.md"
    if not install.is_file() or "3.14" in install.read_text(encoding="utf-8"):
        errors.append("docs/install.md missing or references Python 3.14")
    docs = root / "docs"
    sources = [root / filename for filename in ("README.md", "TOOL_INDEX.md", "SAFETY_MODEL.md")]
    if not docs.is_dir():
        errors.append("docs directory missing")
    else:
        sources.extend(path for path in docs.rglob("*") if path.is_file())
    for path in sources:
        if not path.is_file():
            errors.append(f"tool-count input absent: {path.relative_to(root)}")
        elif re.search(rb"\b(?:13|14) tools\b", path.read_bytes()):
            errors.append(f"stale tool count: {path.relative_to(root)}")
    return errors


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        gate = root / "release-check.sh"
        gate.write_text("\n".join(LOCAL_COMMANDS.values()))
        for name, names in STEPS.items():
            (workflows / name).write_text("\n".join(f"      - name: {x}" for x in names)
                                            + "\n" + "\n".join(CI_COMMANDS[name]))
        for name in CI_ONLY:
            (workflows / name).write_text("# CI-only\n")
        assert not verify(root, check_docs=False), verify(root, check_docs=False)
        original_gate = gate.read_text()
        gate.write_text(original_gate.replace(LOCAL_COMMANDS["skills"], ""))
        assert any("local gate missing skills" in x for x in verify(root, check_docs=False))
        gate.write_text(original_gate)
        path = workflows / "docs-consistency.yml"
        original_workflow = path.read_text()
        path.write_text(original_workflow.replace("      - name: Python version in install.md is not 3.14", ""))
        assert any("workflow steps changed" in x for x in verify(root, check_docs=False))
        path.write_text(original_workflow.replace("./scripts/check-skills.sh", ""))
        assert any("CI command missing" in x for x in verify(root, check_docs=False))
        path.write_text(original_workflow)
        (workflows / "unknown.yml").write_text("on: push\n")
        assert any("undeclared workflow" in x for x in verify(root, check_docs=False))
        gate.write_text(original_gate + "\nbash scripts/validate.sh\n")
        assert any("write-capable" in x for x in verify(root, check_docs=False))
    print("PASS: positive control, removed local/CI check, new workflow, write-capable generator")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(self_test())
    if len(sys.argv) > 1:
        raise SystemExit("usage: check-gate-parity.py [--self-test]")
    problems = verify(ROOT)
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        raise SystemExit(1)
    print("PASS: MCP read-only release gate and CI mappings are current")
