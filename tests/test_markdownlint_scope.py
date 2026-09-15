"""What the markdownlint surface actually covers.

`.markdownlint-cli2.jsonc` lints `**/*.md` and ignored `.venv/**`. The globs are
matched against the whole path, so that pattern excludes only a virtualenv at
the repo root — and mq-mcp's Python project is a subdirectory, so `uv run` there
creates `mq-mcp/.venv` and puts every dependency's documentation into the lint
surface. It reported 111 issues in 18 files, none of them this repo's prose.

CI never saw it, because CI never creates a virtualenv in that directory. That
is the defect: the check is not hermetic, so the same config gives a different
answer depending on whether anyone has run the project locally. A lint that
passes in CI and floods locally teaches people to ignore it.

The config test is cheap and always runs. The behavioural test is the real
proof — it builds the nested layout and asks the linter what it sees — and is
skipped where markdownlint-cli2 cannot be fetched.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".markdownlint-cli2.jsonc"

#: Directories a package manager creates wherever it is run, so they can appear
#: at any depth and must be excluded at any depth.
ANYWHERE = (".venv",)


def _ignores() -> list[str]:
    """Parse the ignores out of the JSONC config, comments and all."""
    text = re.sub(r"^\s*//.*$", "", CONFIG.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return list(json.loads(text)["ignores"])


@pytest.mark.parametrize("directory", ANYWHERE)
def test_a_directory_that_can_appear_anywhere_is_ignored_anywhere(directory):
    """`<dir>/**` anchors at the root; `**/<dir>/**` does not."""
    ignores = _ignores()

    assert f"**/{directory}/**" in ignores, (
        f"{directory} can be created in any subdirectory, so its ignore pattern "
        f"must be anchored with **/ ; found {ignores}"
    )
    assert f"{directory}/**" not in ignores, "the root-only pattern is superseded"


def test_the_lint_surface_is_still_the_whole_repo():
    """The fix must narrow what is ignored, never what is linted."""
    text = re.sub(r"^\s*//.*$", "", CONFIG.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert json.loads(text)["globs"] == ["**/*.md"]


@pytest.mark.skipif(shutil.which("npx") is None, reason="npx is not available")
def test_markdownlint_does_not_see_a_nested_virtualenv(tmp_path):
    """The proof: build the layout and ask the linter what it lints.

    A virtualenv at the repo root and one inside a package directory must both
    be invisible, and ordinary prose beside them must still be linted — a fix
    that hides the noise by narrowing the glob would be worse than the bug.
    """
    shutil.copy(ROOT / ".markdownlint.json", tmp_path / ".markdownlint.json")
    shutil.copy(CONFIG, tmp_path / CONFIG.name)

    broken = "#no space\n\n\n\nand multiple blanks\n"
    for nested in (".venv/lib", "mq-mcp/.venv/lib", "some/deep/path/.venv/lib"):
        directory = tmp_path / nested
        directory.mkdir(parents=True)
        (directory / "dependency.md").write_text(broken, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Title\n\nProse.\n", encoding="utf-8")

    try:
        result = subprocess.run(
            ["npx", "--yes", "markdownlint-cli2"],
            cwd=tmp_path, capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        pytest.skip(f"markdownlint-cli2 could not run: {exc}")

    output = result.stdout + result.stderr
    assert "dependency.md" not in output, "a nested virtualenv reached the lint surface"
    assert re.search(r"Linting: 1 file\b", output), output
    assert result.returncode == 0, output
