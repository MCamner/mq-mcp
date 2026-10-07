from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from review_engine.perception_review import (
    build_review,
    canonical_digest,
    issue_receipt,
    model_evidence,
    validate_perception,
)

ROOT = Path(__file__).resolve().parents[1]


def perception_payload() -> dict:
    core = {
        "schema_version": "perception.v1",
        "source_type": "ui",
        "source_path": "/private/tmp/screen.png",
        "ocr_text": "DELETE",
        "visual_summary": "A destructive action is visible.",
        "detected_regions": [],
        "risk_signals": ["destructive action exposed"],
        "confidence": "high",
        "limitations": ["visual evidence only"],
    }
    return {"evidence_id": canonical_digest(core), **core}


class FakeCompletions:
    def __init__(self, text: str):
        self.text = text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))]
        )


class FakeClient:
    def __init__(self, text: str):
        self.chat = SimpleNamespace(completions=FakeCompletions(text))


def reviewer() -> dict:
    return {
        "schema": "mq.runtime-identity.v1",
        "component": "mq-mcp",
        "version": "2.1.0",
        "commit": "abcdef1",
    }


def contract() -> str:
    return (ROOT / "reviews" / "contracts" / "perception-review.md").read_text(encoding="utf-8")


def test_canonical_perception_schema_is_vendored_from_owner() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "vendor" / "perception.v1.schema.json").read_text(encoding="utf-8")
    )
    assert schema["title"] == "perception.v1"
    assert "evidence_id" in schema["required"]
    assert schema["additionalProperties"] is False


def test_ingress_rejects_tampered_evidence_before_review() -> None:
    payload = perception_payload()
    payload["visual_summary"] = "tampered"
    with pytest.raises(ValueError, match="evidence_id"):
        validate_perception(payload)


def test_review_references_exact_perception_evidence() -> None:
    payload = perception_payload()
    client = FakeClient("[ARCHITECTURE] perception:architecture\nButton placement couples a destructive action to the primary flow.")
    result = build_review(
        payload,
        producer="ui",
        mode="architecture",
        contract=contract(),
        reviewer=reviewer(),
        client=client,
    )
    assert result["schema"] == "mq.perception-review.v1"
    assert result["perception_ref"]["evidence_id"] == payload["evidence_id"]
    assert all(
        finding["evidence_refs"] == [payload["evidence_id"]]
        for finding in result["review"]["findings"]
    )
    assert result["status"] == "WARNING"
    assert result["review"]["model_reinterpretation"] is False


def test_model_receives_no_local_source_path() -> None:
    payload = perception_payload()
    evidence = model_evidence(payload)
    assert "source_path" not in evidence
    client = FakeClient("OK")
    build_review(
        payload,
        producer="ui",
        mode="risk",
        contract=contract(),
        reviewer=reviewer(),
        client=client,
    )
    sent = json.dumps(client.chat.completions.calls[0], default=str)
    assert "/private/tmp/screen.png" not in sent


def test_receipt_contains_only_content_addresses_and_runtime_identity() -> None:
    payload = perception_payload()
    review = build_review(
        payload,
        producer="ui",
        mode="risk",
        contract=contract(),
        reviewer=reviewer(),
        client=FakeClient("OK"),
    )
    receipt = issue_receipt(
        review,
        repository={"repo": "demo", "commit": "0123456789abcdef", "worktree_clean": True},
    )
    assert receipt["status"] == "ISSUED"
    assert receipt["perception_evidence_id"] == payload["evidence_id"]
    assert receipt["review_id"] == review["review_id"]
    serialized = json.dumps(receipt)
    for forbidden in ("source_path", "ocr_text", "detected_regions", "base64", "/private/tmp"):
        assert forbidden not in serialized


def test_receipt_fails_closed_when_requested_repo_commit_is_unknown() -> None:
    review = build_review(
        perception_payload(),
        producer="ui",
        mode="risk",
        contract=contract(),
        reviewer=reviewer(),
        client=FakeClient("OK"),
    )
    receipt = issue_receipt(
        review,
        repository={"repo": "demo", "commit": None, "worktree_clean": None},
    )
    assert receipt["status"] == "REFUSED"
    assert receipt["reason"] == "repository-commit-unavailable"


def test_review_perception_is_in_tool_contract_and_both_client_profiles() -> None:
    contracts = json.loads((ROOT / "docs" / "tool_contracts.json").read_text(encoding="utf-8"))
    tool = next(item for item in contracts["tools"] if item["name"] == "review_perception")
    assert tool["class"] == "B"
    assert tool["resolver"] == "resolve_allowed_local_file"
    assert tool["write"] is False
    assert tool["subprocess"] is True
    for profile_name in ("codex.json", "claude-desktop.json"):
        profile = json.loads((ROOT / "profiles" / profile_name).read_text(encoding="utf-8"))
        assert "review_perception" in profile["recommended_tools"]
