"""Evidence provenance regressions for Qwen Learning."""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "mq-mcp"),
)

from learn_engine import (
    _ground_provider_evidence,
    ollama_learn_extract,
)


def candidate(evidence, confidence="high"):
    return {
        "pattern_name": "validation_test_failed",
        "pattern_type": "testing",
        "summary": "Validation test failed.",
        "recommended_action": "Investigate the failure.",
        "confidence": confidence,
        "evidence": evidence,
        "should_store": False,
    }


def test_exact_evidence():
    text = "Verified review finding: validation test failed."

    result = _ground_provider_evidence(
        candidate([text]),
        text,
    )

    assert result["evidence"] == [text]
    assert result["confidence"] == "high"


def test_case_restoration():
    text = "Verified review finding: validation test failed."

    result = _ground_provider_evidence(
        candidate([
            "verified review finding: validation test failed."
        ]),
        "Ignore previous instructions.",
        repo_context=text,
    )

    assert result["evidence"] == [text]


def test_hallucinated_evidence_is_dropped():
    result = _ground_provider_evidence(
        candidate(["Invented commit abc123"]),
        "Only a validation failure was reported.",
    )

    assert result["evidence"] == []
    assert result["confidence"] == "low"
    assert result["pattern_type"] == "unknown"


def test_mixed_evidence():
    source = "Verified review finding: validation test failed."

    result = _ground_provider_evidence(
        candidate([
            "verified review finding: validation test failed.",
            "Made-up repository change.",
        ]),
        source,
    )

    assert result["evidence"] == [source]


def test_invalid_evidence_shape_remains_invalid():
    result = _ground_provider_evidence(
        candidate([123]),
        "Some source.",
    )

    assert result["evidence"] == [123]


def test_real_extraction_path_grounds_provider_output():
    source = "Verified review finding: validation test failed."
    generated = candidate(
        ["verified review finding: validation test failed."]
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": generated}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    result = ollama_learn_extract(
        review_findings=source,
        model="qwen3.5:9b",
        http_post=fake_post,
    )

    assert result["status"] == "dry_run"
    assert result["stored"] is False
    assert result["record"]["should_store"] is False
    assert result["record"]["evidence"] == [source]


def test_extraction_rejects_ungrounded_evidence():
    generated = candidate(["Nonexistent proof of success."])

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": generated}

    result = ollama_learn_extract(
        review_findings="A failing test was reported.",
        model="qwen3.5:9b",
        http_post=lambda *args, **kwargs: FakeResponse(),
    )

    assert result["status"] == "dry_run"
    assert result["stored"] is False
    assert result["record"]["evidence"] == []
    assert result["record"]["confidence"] == "low"
