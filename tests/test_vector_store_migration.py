import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASK_PATH = ROOT / "mq-mcp" / "ask.py"
UPLOAD_PATH = ROOT / "scripts" / "upload_vector_pack.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ask(monkeypatch):
    monkeypatch.delenv("MQ_MCP_VECTOR_STORE_ID", raising=False)
    monkeypatch.delenv("OPENAI_VECTOR_STORE_ID", raising=False)
    monkeypatch.delenv("OPENAI_SEMANTIC_MEMORY_ID", raising=False)
    return _load(ASK_PATH, "mq_mcp_ask_vector_store_test")


def test_ask_defaults_to_canonical_store(ask):
    store_ids, _system, label = ask.resolve_store_ids()

    assert store_ids == [ask.CANONICAL_VECTOR_STORE_ID]
    assert label == "canonical memory"


def test_retired_openai_vector_store_env_no_longer_steers_ask(ask, monkeypatch):
    monkeypatch.setenv("OPENAI_VECTOR_STORE_ID", "vs_retired_or_unrelated")

    assert ask.resolve_local_vector_store_id() == ask.CANONICAL_VECTOR_STORE_ID


def test_explicit_mq_mcp_override_wins(ask, monkeypatch):
    monkeypatch.setenv("MQ_MCP_VECTOR_STORE_ID", "vs_explicit")

    store_ids, _system, label = ask.resolve_store_ids()

    assert store_ids == ["vs_explicit", ask.CANONICAL_VECTOR_STORE_ID]
    assert label == "local + global"


def test_canonical_global_store_is_not_duplicated(ask, monkeypatch):
    monkeypatch.setenv(
        "OPENAI_SEMANTIC_MEMORY_ID",
        ask.CANONICAL_VECTOR_STORE_ID,
    )

    store_ids, _system, _label = ask.resolve_store_ids()

    assert store_ids == [ask.CANONICAL_VECTOR_STORE_ID]


def test_global_only_defaults_to_canonical_store(ask):
    store_ids, system, label = ask.resolve_store_ids(global_only=True)

    assert store_ids == [ask.CANONICAL_VECTOR_STORE_ID]
    assert system == ask.SYSTEM_GLOBAL
    assert label == "global memory"


def test_full_pack_uploader_refuses_shared_canonical_store(monkeypatch):
    upload = _load(UPLOAD_PATH, "mq_mcp_upload_vector_pack_test")
    monkeypatch.setenv(
        "MQ_MCP_VECTOR_STORE_ID",
        upload.CANONICAL_VECTOR_STORE_ID,
    )

    with pytest.raises(SystemExit, match="Refusing full-store replacement"):
        upload.resolve_target_store()
