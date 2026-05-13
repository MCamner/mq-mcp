import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"


def _load_server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _load_server()


# --- resolve_repo_file ---

def test_resolve_repo_file_allows_readme():
    target = server.resolve_repo_file("README.md")
    assert target == (ROOT / "README.md").resolve()


def test_resolve_repo_file_blocks_parent_escape():
    with pytest.raises(ValueError, match="Blocked path outside repo"):
        server.resolve_repo_file("../outside.txt")


def test_resolve_repo_file_blocks_absolute_path():
    with pytest.raises(ValueError, match="Blocked path outside repo"):
        server.resolve_repo_file("/etc/passwd")


# --- update_repo_file ---

def test_update_repo_file_blocks_env_file():
    result = server.update_repo_file(".env", "x", "y")
    assert "Blocked file" in result


def test_update_repo_file_blocks_git_dir():
    result = server.update_repo_file(".git/config", "x", "y")
    assert "Blocked" in result


def test_update_repo_file_blocks_unsupported_suffix():
    result = server.update_repo_file("file.pdf", "x", "y")
    assert "Blocked file type" in result


def test_update_repo_file_rejects_empty_old_text():
    result = server.update_repo_file("README.md", "", "something")
    assert "old_text must not be empty" in result


def test_update_repo_file_no_match_returns_error():
    result = server.update_repo_file("README.md", "definitely-not-present-xyz-abc-123", "y")
    assert "No exact match found" in result


def test_update_repo_file_refuses_ambiguous_match():
    result = server.update_repo_file("README.md", "mq-mcp", "replacement")
    assert "matched" in result and "times" in result


# --- read_repo_file ---

def test_read_repo_file_reads_readme():
    result = server.read_repo_file("README.md")
    assert "mq-mcp" in result


def test_read_repo_file_missing_file():
    result = server.read_repo_file("nonexistent_xyz_abc.md")
    assert "not found" in result.lower()


# --- list_repo_files ---

def test_list_repo_files_includes_readme():
    result = server.list_repo_files()
    assert "README.md" in result


def test_list_repo_files_excludes_git_dir():
    result = server.list_repo_files()
    lines = result.split("\n")
    assert not any(line == ".git" or line.startswith(".git/") for line in lines)
