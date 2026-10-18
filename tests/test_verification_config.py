"""Verification rules must point at real checks and catch README regressions."""
from __future__ import annotations

import ast
import fnmatch
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_readme_has_real_checks_and_history_is_separate():
    config = json.loads((ROOT / ".mq/verification.json").read_text())
    selected = [c for c in config["checks"] if any(fnmatch.fnmatchcase("README.md", p) for p in c["paths"])]
    targets = {p for c in selected for p in c["targets"]}
    assert {"scripts/check-runtime-truth.sh", "scripts/check-mcp-tool-docs.sh"} <= targets
    assert config["runtime_data"] == [{
        "path": "review_engine/memory/review_history.json",
        "reason": "Generated review history; inspect separately from source verification.",
    }]
    for check in config["checks"]:
        for target in check["targets"]:
            assert (ROOT / target).is_file(), target


@pytest.fixture
def docs_repo(tmp_path):
    inputs = ["scripts/check-runtime-truth.sh", "scripts/check-mcp-tool-docs.sh",
              "VERSION", "README.md", "CHANGELOG.md", "mq-mcp/server.py",
              "docs/stability.json", "docs/TOOL_SAFETY.md", "docs/tool_contracts.json"]
    for name in inputs:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def run_check(root, script):
    return subprocess.run(["bash", str(root / "scripts" / script)], cwd=root,
                          capture_output=True, text=True, timeout=20)


@pytest.mark.parametrize("script", ["check-runtime-truth.sh", "check-mcp-tool-docs.sh"])
def test_readme_check_positive_control(docs_repo, script):
    result = run_check(docs_repo, script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_readme_version_regression_fails(docs_repo):
    version = (docs_repo / "VERSION").read_text().strip()
    p = docs_repo / "README.md"
    text = p.read_text()
    assert "version-" + version + "-" in text
    p.write_text(text.replace("version-" + version + "-", "version-0.0.0-"))
    result = run_check(docs_repo, "check-runtime-truth.sh")
    assert result.returncode == 1
    assert "README badge" in result.stdout + result.stderr


def test_readme_missing_tool_documentation_fails(docs_repo):
    tree = ast.parse((docs_repo / "mq-mcp/server.py").read_text())
    tool = next(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                        and d.func.attr == "tool" for d in n.decorator_list))
    p = docs_repo / "README.md"
    assert tool in p.read_text()
    p.write_text(p.read_text().replace(tool, "removed-reference"))
    result = run_check(docs_repo, "check-mcp-tool-docs.sh")
    assert result.returncode == 1
    assert tool + " missing from README.md" in result.stdout + result.stderr
