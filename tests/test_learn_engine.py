import json
from pathlib import Path

import pytest


def _load_engine():
    import importlib.util
    import sys

    module_path = Path(__file__).resolve().parents[1] / "mq-mcp" / "learn_engine.py"
    spec = importlib.util.spec_from_file_location("learn_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve cls.__module__ in sys.modules
    # (required in Python 3.14+).
    sys.modules["learn_engine"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_record_and_search_learning(tmp_path):
    engine = _load_engine()
    record = engine.make_learning(
        tmp_path,
        repo="mq-mcp",
        source="codex",
        task="Fix docs drift",
        lesson="Keep tool docs and runtime tool count in sync.",
        validation=["validate passes", "release-check passes"],
        tags=["docs", "release"],
        risk="low",
    )

    result = engine.record_learning(tmp_path, record)
    assert result["status"] == "ok"

    matches = engine.search_learnings(tmp_path, "tool count")
    assert len(matches) == 1
    assert matches[0]["task"] == "Fix docs drift"

    summary = engine.summarize_learnings(tmp_path)
    assert "Fix docs drift" in summary
    assert "Keep tool docs" in summary


def test_learning_redacts_secrets_before_storage(tmp_path):
    engine = _load_engine()
    record = engine.make_learning(
        tmp_path,
        repo="mq-mcp",
        source="manual",
        task="Secret handling",
        lesson="Never store api_key=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789 in lessons.",
        validation="redaction checked",
        commands_used=["export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789"],
        risk="medium",
    )
    engine.record_learning(tmp_path, record)

    raw = engine.learning_store_path(tmp_path).read_text(encoding="utf-8")
    assert "sk-proj-" not in raw
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in raw
    assert "<redacted>" in raw


def test_promotion_preview_does_not_write_target_files(tmp_path):
    engine = _load_engine()
    record = engine.make_learning(
        tmp_path,
        repo="mq-mcp",
        source="review",
        task="Promote safely",
        lesson="Promotion starts as dry-run preview.",
        validation="preview only",
        risk="low",
    )
    engine.record_learning(tmp_path, record)

    preview = engine.promotion_preview(tmp_path, record.id, "runbook")
    assert "Learning promotion preview" in preview
    assert "docs/RUNBOOK.md" in preview
    assert not (tmp_path / "docs" / "RUNBOOK.md").exists()


def test_learning_rejects_unsupported_source_and_risk(tmp_path):
    engine = _load_engine()
    with pytest.raises(ValueError):
        engine.make_learning(
            tmp_path,
            repo="mq-mcp",
            source="unsafe-agent",
            task="x",
            lesson="x",
            validation="x",
        )

    with pytest.raises(ValueError):
        engine.make_learning(
            tmp_path,
            repo="mq-mcp",
            source="codex",
            task="x",
            lesson="x",
            validation="x",
            risk="critical",
        )


def test_learning_schema_accepts_example_shape(tmp_path):
    engine = _load_engine()
    record = engine.make_learning(
        tmp_path,
        repo="mq-mcp",
        source="diff",
        task="Schema shape",
        lesson="Learning records are JSON serializable.",
        validation=["json dumps works"],
        risk="unknown",
    )
    payload = record.to_dict()
    serialized = json.dumps(payload)
    assert payload["id"].startswith("learn_")
    assert "Learning records" in serialized
