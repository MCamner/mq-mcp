"""The registry must report the review tools' key requirement the way the
review runtime decides it: OpenAI unless MQ_MCP_REVIEW_PROVIDER=ollama."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("mq_tool_registry_key", ROOT / "mq-mcp" / "tool_registry.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _review_entry():
    return next(t for t in _mod.load_registry() if t["name"] == "review_file")


def test_review_requires_key_when_provider_unset(monkeypatch):
    monkeypatch.delenv("MQ_MCP_REVIEW_PROVIDER", raising=False)
    from review_engine.model_runtime import review_requires_key
    assert review_requires_key() is True
    assert _review_entry()["requires_api_key"] is True


def test_review_needs_no_key_with_local_provider(monkeypatch):
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "ollama")
    assert _review_entry()["requires_api_key"] is False
