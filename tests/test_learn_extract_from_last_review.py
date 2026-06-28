"""Tests for learn_extract_from_last_review in learn_engine.py."""
import importlib.util
import json
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


_VALID_CANDIDATE = {
    "pattern_name": "release-gate-contracts",
    "pattern_type": "release",
    "summary": "mq-agent needs release_gate_v2.schema.json even without MCP tools.",
    "recommended_action": "Copy schema from mq-mcp to contracts/ in orchestration repos.",
    "evidence": ["check_contracts_valid raised BLOCKED/68 without schema file"],
    "should_store": False,
    "confidence": "high",
}

_VALID_REPO_CONTEXT = "check_contracts_valid raised BLOCKED/68 without schema file"


def _ok_http_post(*a, **k):
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps(_VALID_CANDIDATE)}

    return _Resp()


def test_learn_extract_from_last_review_dry_run():
    engine = _load_engine()
    loader = lambda path: "BLOCKER: missing contracts schema in mq-agent."
    result = engine.learn_extract_from_last_review(
        "mq-agent/contracts/release_gate_v2.schema.json",
        review_loader=loader,
        repo_context=_VALID_REPO_CONTEXT,
        http_post=_ok_http_post,
    )
    assert result["status"] == "dry_run"
    assert result["stored"] is False
    assert result["file"] == "mq-agent/contracts/release_gate_v2.schema.json"
    assert result["record"]["pattern_name"] == "release-gate-contracts"


def test_learn_extract_from_last_review_no_history():
    engine = _load_engine()
    loader = lambda path: None
    result = engine.learn_extract_from_last_review(
        "some/unreviewed/file.py",
        review_loader=loader,
        http_post=_ok_http_post,
    )
    assert result["status"] == "no_review"
    assert "some/unreviewed/file.py" in result["reason"]
    assert result["file"] == "some/unreviewed/file.py"


def test_learn_extract_from_last_review_ollama_unavailable():
    engine = _load_engine()
    loader = lambda path: "some review findings"

    def _fail(*a, **k):
        raise ConnectionError("connection refused")

    result = engine.learn_extract_from_last_review(
        "mq-mcp/server.py",
        review_loader=loader,
        http_post=_fail,
    )
    assert result["status"] == "unavailable"
    assert result["file"] == "mq-mcp/server.py"


def test_learn_extract_from_last_review_preserves_file_on_unavailable():
    engine = _load_engine()
    loader = lambda path: "findings"

    def _fail(*a, **k):
        raise ConnectionError("down")

    result = engine.learn_extract_from_last_review(
        "path/to/file.py",
        review_loader=loader,
        http_post=_fail,
    )
    assert result.get("file") == "path/to/file.py"


def test_learn_extract_from_last_review_does_not_store():
    engine = _load_engine()
    loader = lambda path: "important review findings"
    result = engine.learn_extract_from_last_review(
        "mq-mcp/learn_engine.py",
        review_loader=loader,
        repo_context=_VALID_REPO_CONTEXT,
        http_post=_ok_http_post,
    )
    assert result.get("stored") is False
