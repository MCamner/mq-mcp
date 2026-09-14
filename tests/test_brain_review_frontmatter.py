"""Review-frontmatter projection for admitted brain-ingress provenance."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mq-mcp"))

from runtime.memory.obsidian_writer import record_review


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    return tmp_path


def _write_review(vault: Path, producer: dict | None) -> str:
    decision = "accept" if producer is not None else "accept_with_warning"
    result = record_review(
        source="mq-agent/signal",
        finding_count=0,
        top_risks=[],
        suggested_next_steps=[],
        provenance={
            "decision": decision,
            "reasons": [] if producer is not None else ["producer-not-supplied"],
            "findings": [],
            "producer": producer,
            "receiver_observation": None,
        },
    )
    assert result["ok"] is True
    return Path(result["path"]).read_text(encoding="utf-8")


def test_valid_producer_is_projected_to_review_frontmatter(vault: Path) -> None:
    content = _write_review(
        vault,
        {
            "component": "mq-agent",
            "version": "1.28.0",
            "commit": "df6014feaa49b8a525f2d7f236cc246836eaa4f6",
            "identity_quality": "verified",
        },
    )

    frontmatter = content.split("---", 2)[1]
    assert "ingress_decision: accept" in frontmatter
    assert "producer_component: mq-agent" in frontmatter
    assert "producer_version: 1.28.0" in frontmatter
    assert "producer_commit: df6014feaa49b8a525f2d7f236cc246836eaa4f6" in frontmatter
    assert "producer_identity_quality: verified" in frontmatter


def test_missing_producer_does_not_invent_frontmatter_identity(vault: Path) -> None:
    content = _write_review(vault, None)

    frontmatter = content.split("---", 2)[1]
    assert "ingress_decision: accept_with_warning" in frontmatter
    assert "producer_" not in frontmatter


def test_partial_producer_omits_unknown_values(vault: Path) -> None:
    content = _write_review(
        vault,
        {
            "component": "mq-agent",
            "version": "1.28.0",
            "commit": None,
            "identity_quality": "partial",
        },
    )

    frontmatter = content.split("---", 2)[1]
    assert "producer_component: mq-agent" in frontmatter
    assert "producer_version: 1.28.0" in frontmatter
    assert "producer_identity_quality: partial" in frontmatter
    assert "producer_commit:" not in frontmatter
