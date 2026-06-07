"""Unit tests for runtime.memory.obsidian_writer."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure mq-mcp package is importable from the test runner.
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "mq-mcp"))

from runtime.memory.obsidian_writer import (
    record_decision,
    record_learning,
    record_review,
    record_session,
    vault_exists,
    vault_path,
)


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    return tmp_path


def test_vault_exists_true(vault: Path) -> None:
    assert vault_exists() is True


def test_vault_exists_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path / "nonexistent"))
    assert vault_exists() is False


def test_vault_path_uses_env(vault: Path) -> None:
    assert vault_path() == vault


def test_record_review_creates_file(vault: Path) -> None:
    result = record_review(
        source="mq-mcp/server.py",
        finding_count=2,
        top_risks=["[HIGH] unused import"],
        suggested_next_steps=["remove import"],
        confidence="high",
        raw_summary="full text here",
    )
    assert result["ok"] is True
    created = Path(result["path"])
    assert created.exists()
    assert created.parent == vault / "reviews"
    content = created.read_text()
    assert "review.v1" in content
    assert "mq-mcp/server.py" in content
    assert "HIGH" in content


def test_record_review_missing_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path / "missing"))
    result = record_review("src/x.py", 0, [], [])
    assert result["ok"] is False
    assert "Vault not found" in result["error"]


def test_record_learning_creates_file(vault: Path) -> None:
    result = record_learning(
        pattern_name="release-gate-contracts",
        pattern_type="release",
        summary="mq-agent needs schema file.",
        evidence=["check_contracts_valid raised BLOCKED/68"],
        recommended_action="copy schema from mq-mcp",
        confidence="high",
    )
    assert result["ok"] is True
    created = Path(result["path"])
    assert created.exists()
    assert created.parent == vault / "learn"
    content = created.read_text()
    assert "learn.v1" in content
    assert "release-gate-contracts" in content


def test_record_learning_overwrites_same_pattern(vault: Path) -> None:
    record_learning("dup-pattern", "testing", "v1", [], "action1")
    result = record_learning("dup-pattern", "testing", "v2 updated", [], "action2")
    assert result["ok"] is True
    content = Path(result["path"]).read_text()
    assert "v2 updated" in content
    assert len(list((vault / "learn").glob("dup-pattern.md"))) == 1


def test_record_session_creates_file(vault: Path) -> None:
    result = record_session(
        title="mq brain kickoff",
        summary="set up the brain pipeline",
        repos=["mq-agent", "mq-mcp"],
        outcomes=["brain flag added"],
        follow_ups=["add decide command"],
    )
    assert result["ok"] is True
    created = Path(result["path"])
    assert created.exists()
    assert created.parent == vault / "sessions"
    content = created.read_text()
    assert "session.v1" in content
    assert "mq brain kickoff" in content
    assert "mq-agent" in content


def test_record_decision_creates_file(vault: Path) -> None:
    result = record_decision(
        title="Use obsidian for second brain",
        context="need local-first knowledge store",
        decision="write to mqobsidian vault",
        rationale="already in use, no new infra",
        consequences="tied to Obsidian sync",
        tags=["architecture", "brain"],
    )
    assert result["ok"] is True
    created = Path(result["path"])
    assert created.exists()
    assert created.parent == vault / "decisions"
    content = created.read_text()
    assert "decision.v1" in content
    assert "Use obsidian for second brain" in content
    assert "architecture" in content


def test_record_decision_optional_consequences_omitted(vault: Path) -> None:
    result = record_decision(
        title="Skip caching layer",
        context="latency is acceptable",
        decision="no cache",
        rationale="complexity outweighs gain",
    )
    assert result["ok"] is True
    content = Path(result["path"]).read_text()
    assert "Consequences" not in content
