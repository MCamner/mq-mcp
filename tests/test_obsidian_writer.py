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
    promote_learning,
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


# ── promote_learning ────────────────────────────────────────────────────────

_VALID_LEARN_CONTENT = """\
---
schema_version: learn.v1
written_by: mq-mcp/obsidian_writer
timestamp: 2026-06-08T00:00:00Z
pattern_name: test-pattern
pattern_type: release
confidence: high
---
# Pattern: test-pattern

## Overview

**Type:** release

## Summary

Always verify git tags match gh releases.

## Evidence

- Fixed by running gh release create after git tag

## Recommended action

After tagging, run gh release list to confirm the release exists.
"""


def test_promote_learning_creates_verified_file(vault: Path) -> None:
    learn_dir = vault / "learn"
    learn_dir.mkdir()
    (learn_dir / "test-pattern.md").write_text(_VALID_LEARN_CONTENT)

    result = promote_learning("test-pattern")

    assert result["ok"] is True
    verified_dir = vault / "learn" / "verified"
    assert verified_dir.exists()
    promoted_files = list(verified_dir.glob("*test-pattern.md"))
    assert len(promoted_files) == 1
    content = promoted_files[0].read_text()
    assert "status: verified" in content
    assert "promoted_at:" in content
    assert "promoted_from: learn/test-pattern.md" in content


def test_promote_learning_marks_original_as_promoted(vault: Path) -> None:
    learn_dir = vault / "learn"
    learn_dir.mkdir()
    source = learn_dir / "test-pattern.md"
    source.write_text(_VALID_LEARN_CONTENT)

    promote_learning("test-pattern")

    original = source.read_text()
    assert "status: promoted" in original


def test_promote_learning_accepts_learn_prefix_and_md_suffix(vault: Path) -> None:
    (vault / "learn").mkdir()
    (vault / "learn" / "test-pattern.md").write_text(_VALID_LEARN_CONTENT)

    r1 = promote_learning("learn/test-pattern.md")
    assert r1["ok"] is True


def test_promote_learning_fails_missing_fields(vault: Path) -> None:
    (vault / "learn").mkdir()
    (vault / "learn" / "incomplete.md").write_text(
        "---\nschema_version: learn.v1\n---\n## Summary\n\ntext\n\n## Evidence\n\n- x\n\n## Recommended action\n\nfix it\n"
    )
    result = promote_learning("incomplete")
    assert result["ok"] is False
    assert "pattern_name" in result["error"]


def test_promote_learning_fails_missing_sections(vault: Path) -> None:
    (vault / "learn").mkdir()
    (vault / "learn" / "no-sections.md").write_text(
        "---\npattern_name: x\npattern_type: release\n---\n# Pattern: x\n\nNo required sections here.\n"
    )
    result = promote_learning("no-sections")
    assert result["ok"] is False
    assert "Missing required sections" in result["error"]


def test_promote_learning_fails_if_slug_not_found(vault: Path) -> None:
    (vault / "learn").mkdir()
    result = promote_learning("nonexistent-slug")
    assert result["ok"] is False
    assert "Not found" in result["error"]
