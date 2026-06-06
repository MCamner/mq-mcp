"""Tests for ollama_learn_status in learn_engine.py."""
import importlib.util
import sys
from pathlib import Path


def _load_engine():
    module_path = Path(__file__).resolve().parents[1] / "mq-mcp" / "learn_engine.py"
    spec = importlib.util.spec_from_file_location("learn_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["learn_engine"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _OkResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"models": [{"name": "mq-learn:latest"}]}


class _MissingModelResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"models": [{"name": "llama3.2:latest"}]}


class _EmptyModelsResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"models": []}


def test_ollama_learn_status_ready():
    engine = _load_engine()
    result = engine.ollama_learn_status(http_get=lambda *a, **k: _OkResponse())
    assert result["status"] == "ready"
    assert result["model"] == "mq-learn"
    assert result["mode"] == "optional"
    assert result["schema"] == "schemas/learn_extraction.schema.json"
    assert "dry-run" in result["storage"]


def test_ollama_learn_status_missing_model():
    engine = _load_engine()
    result = engine.ollama_learn_status(http_get=lambda *a, **k: _MissingModelResponse())
    assert result["status"] == "unavailable"
    assert "not found" in result["reason"]
    assert "mq-learn" in result["reason"]
    assert "llama3.2" in result.get("available_models", [])


def test_ollama_learn_status_no_models():
    engine = _load_engine()
    result = engine.ollama_learn_status(http_get=lambda *a, **k: _EmptyModelsResponse())
    assert result["status"] == "unavailable"
    assert result.get("available_models") == []


def test_ollama_learn_status_connection_error():
    engine = _load_engine()

    def _fail(*a, **k):
        raise ConnectionError("connection refused")

    result = engine.ollama_learn_status(http_get=_fail)
    assert result["status"] == "unavailable"
    assert "unavailable" in result["reason"].lower()


def test_ollama_learn_status_custom_model():
    engine = _load_engine()

    class _CustomModelResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "my-model:latest"}]}

    result = engine.ollama_learn_status(
        http_get=lambda *a, **k: _CustomModelResponse(),
        model="my-model",
    )
    assert result["status"] == "ready"
    assert result["model"] == "my-model"


def test_ollama_learn_status_does_not_write(tmp_path):
    """Confirm that ollama_learn_status makes no filesystem writes."""
    engine = _load_engine()
    before = list(tmp_path.rglob("*"))
    engine.ollama_learn_status(http_get=lambda *a, **k: _OkResponse())
    after = list(tmp_path.rglob("*"))
    assert before == after
