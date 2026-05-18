import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_allowed", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

resolve_allowed_local_file = _mod.resolve_allowed_local_file
allowed_external_roots = _mod.allowed_external_roots


def test_resolve_allowed_local_file_allows_repo_relative():
    target = resolve_allowed_local_file("README.md")
    assert target == (ROOT / "README.md").resolve()


def test_resolve_allowed_local_file_blocks_external_without_allowlist(monkeypatch, tmp_path):
    external = tmp_path / "outside.txt"
    external.write_text("outside", encoding="utf-8")
    monkeypatch.delenv("MQ_MCP_ALLOWED_PATHS", raising=False)
    with pytest.raises(ValueError, match="Blocked path"):
        resolve_allowed_local_file(str(external))


def test_resolve_allowed_local_file_allows_external_with_allowlist(monkeypatch, tmp_path):
    external = tmp_path / "allowed.txt"
    external.write_text("allowed", encoding="utf-8")
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(tmp_path))
    target = resolve_allowed_local_file(str(external))
    assert target == external.resolve()


def test_resolve_allowed_local_file_blocks_sibling_of_allowed_root(monkeypatch, tmp_path):
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    external = blocked_dir / "secret.txt"
    external.write_text("secret", encoding="utf-8")
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", str(allowed_dir))
    with pytest.raises(ValueError, match="Blocked path"):
        resolve_allowed_local_file(str(external))


def test_allowed_external_roots_empty_without_env(monkeypatch):
    monkeypatch.delenv("MQ_MCP_ALLOWED_PATHS", raising=False)
    assert allowed_external_roots() == []


def test_allowed_external_roots_parses_colon_separated_paths(monkeypatch, tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", f"{first}:{second}")
    roots = allowed_external_roots()
    assert first.resolve() in roots
    assert second.resolve() in roots


def test_allowed_external_roots_ignores_empty_segments(monkeypatch, tmp_path):
    first = tmp_path / "real"
    first.mkdir()
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", f":{first}:")
    roots = allowed_external_roots()
    assert first.resolve() in roots
    assert len(roots) == 1
