"""Regression tests for Bridget's MCP subprocess environment boundary."""

import os

from bridge import mcp_child_env


def test_child_env_only_forwards_server_allowlist(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-forward")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-forward")
    monkeypatch.setenv("OPENAI_API_KEY", "test-value")
    monkeypatch.setenv("MQ_MCP_ALLOWED_PATHS", "/tmp/allowed")
    monkeypatch.setenv("MQ_MCP_ALLOW_SHELL_EXEC", "1")

    env = mcp_child_env(do_mode=False)

    assert env["OPENAI_API_KEY"] == "test-value"
    assert env["MQ_MCP_ALLOWED_PATHS"] == "/tmp/allowed"
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "MQ_MCP_ALLOW_SHELL_EXEC" not in env


def test_do_mode_flag_is_scoped_to_child(monkeypatch):
    monkeypatch.delenv("MQ_MCP_ALLOW_SHELL_EXEC", raising=False)

    assert mcp_child_env(do_mode=True)["MQ_MCP_ALLOW_SHELL_EXEC"] == "1"
    assert "MQ_MCP_ALLOW_SHELL_EXEC" not in os.environ
    assert "MQ_MCP_ALLOW_SHELL_EXEC" not in mcp_child_env(do_mode=False)
