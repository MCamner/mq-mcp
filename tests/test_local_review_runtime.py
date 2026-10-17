from __future__ import annotations

import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_default_review_requires_openai_credentials(monkeypatch):
    from review_engine.model_runtime import review_client, review_model
    monkeypatch.delenv("MQ_MCP_REVIEW_PROVIDER", raising=False)
    monkeypatch.delenv("MQ_MCP_REVIEW_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "cloud-model-must-not-leak")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cloud = SimpleNamespace(OpenAI=MagicMock(side_effect=AssertionError("cloud called")))
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        review_client(cloud)
    assert review_model() == "cloud-model-must-not-leak"
    cloud.OpenAI.assert_not_called()


def test_local_failure_never_falls_back_to_openai(monkeypatch):
    from review_engine import model_runtime as runtime
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "ollama")
    cloud = SimpleNamespace(OpenAI=MagicMock())
    client = runtime.review_client(cloud)
    monkeypatch.setattr(runtime.urllib.request, "urlopen", MagicMock(side_effect=urllib.error.URLError("offline")))
    with pytest.raises(urllib.error.URLError):
        client.chat.completions.create(model="qwen3.5:9b", messages=[{"role":"user","content":"review"}])
    cloud.OpenAI.assert_not_called()


def test_cloud_requires_explicit_provider(monkeypatch):
    from review_engine.model_runtime import review_client, review_model, review_requires_key
    monkeypatch.setenv("MQ_MCP_REVIEW_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("OPENAI_MODEL", "cloud-test")
    cloud = SimpleNamespace(OpenAI=MagicMock())
    assert review_requires_key() is True
    assert review_model() == "cloud-test"
    assert review_client(cloud) == cloud.OpenAI.return_value
    cloud.OpenAI.assert_called_once_with(api_key="test-only")


def test_native_review_disables_thinking_and_requires_complete_output(monkeypatch):
    from review_engine import model_runtime as runtime
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"done":true,"done_reason":"stop","message":{"content":"OK"}}'
    opened = MagicMock(return_value=response)
    monkeypatch.setattr(runtime.urllib.request, "urlopen", opened)
    client = runtime.OllamaClient()
    result = client.chat.completions.create(model="qwen3.5:9b", messages=[{"role":"user","content":"review"}], max_tokens=100)
    payload = json.loads(opened.call_args.args[0].data)
    assert payload["think"] is False
    assert payload["options"]["num_predict"] == 100
    assert result.choices[0].message.content == "OK"
    response.__enter__.return_value.read.return_value = b'{"done":true,"done_reason":"length","message":{"content":"partial"}}'
    with pytest.raises(ValueError, match="incomplete"):
        client.chat.completions.create(model="qwen3.5:9b", messages=[])
