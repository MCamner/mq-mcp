import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resolve_repo_file_allows_readme(server):
    target = server.resolve_repo_file("README.md")
    assert target == (ROOT / "README.md").resolve()


def test_resolve_repo_file_blocks_parent_escape(server):
    with pytest.raises(ValueError, match="Blocked path outside repo"):
        server.resolve_repo_file("../outside.txt")


def test_resolve_repo_file_blocks_absolute_path(server):
    with pytest.raises(ValueError, match="Blocked path outside repo"):
        server.resolve_repo_file("/etc/passwd")


@pytest.mark.parametrize("path", [".env", ".env.local", ".envrc", "uv.lock"])
def test_update_repo_file_blocks_secret_files(server, path):
    result = server.update_repo_file(path, "x", "y")
    assert "Blocked file" in result


@pytest.mark.parametrize("path", [
    ".git/config",
    ".venv/lib/something.py",
    "__pycache__/module.cpython-314.pyc",
    "node_modules/pkg/index.js",
])
def test_update_repo_file_blocks_system_dirs(server, path):
    result = server.update_repo_file(path, "x", "y")
    assert "Blocked" in result


def test_update_repo_file_blocks_unsupported_suffix(server):
    result = server.update_repo_file("docs/install.pdf", "x", "y")
    assert "Blocked file type" in result


def test_update_repo_file_rejects_empty_old_text(server):
    result = server.update_repo_file("README.md", "", "something")
    assert "old_text must not be empty" in result


def test_update_repo_file_no_match_returns_error(server):
    result = server.update_repo_file("README.md", "definitely-not-present-xyz-abc-123", "y")
    assert "No exact match found" in result


def test_update_repo_file_refuses_ambiguous_match(server):
    result = server.update_repo_file("README.md", "##", "replacement")
    assert "matched" in result and "times" in result


def test_analyze_csv_blocks_parent_escape(server):
    result = server.analyze_csv("../../../etc/passwd")
    assert "Blocked path outside repo" in result


def test_read_repo_file_reads_readme(server):
    result = server.read_repo_file("README.md")
    assert "mq-mcp" in result


def test_read_repo_file_missing_file(server):
    result = server.read_repo_file("nonexistent_xyz_abc.md")
    assert "not found" in result.lower()


def test_list_repo_files_includes_readme(server):
    result = server.list_repo_files()
    assert "README.md" in result


def test_list_repo_files_excludes_git_dir(server):
    result = server.list_repo_files()
    lines = result.split("\n")
    assert not any(line == ".git" or line.startswith(".git/") for line in lines)
