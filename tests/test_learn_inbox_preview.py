import json
from pathlib import Path


def _load_engine():
    import importlib.util
    import sys

    module_path = Path(__file__).resolve().parents[1] / "mq-mcp" / "learn_engine.py"
    spec = importlib.util.spec_from_file_location("learn_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["learn_engine"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _seed_inbox(engine, repo_root: Path, rows: list[dict]) -> Path:
    path = engine.inbox_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


# --- build_record_learning_draft: pure mapping --------------------------------


def test_normal_candidate_concrete_action_becomes_task():
    engine = _load_engine()
    candidate = {
        "pattern_name": "release-gate-v2",
        "summary": "Release gate v2 must run lint and type checks before tagging.",
        "evidence": ["scripts/release-check.sh", "CHANGELOG.md"],
        "recommended_action": "Run the release gate before every version tag",
        "confidence": "high",
    }
    out = engine.build_record_learning_draft(candidate)
    assert out["candidate"] == "release-gate-v2"
    assert out["write_performed"] is False
    draft = out["draft"]
    # Concrete recommended_action is used verbatim as the task.
    assert draft["task"] == "Run the release gate before every version tag"
    assert draft["repo"] == "mq-mcp"
    assert draft["source"] == "manual"
    assert draft["risk"] == "low"
    assert draft["tags"] == ["release", "gate"]


def test_missing_recommended_action_falls_back_to_pattern_task():
    engine = _load_engine()
    candidate = {
        "pattern_name": "orchestration_contract_update",
        "summary": "Keep the orchestration contract and its docs in sync.",
        "evidence": ["docs/ORCHESTRATION.md"],
    }
    out = engine.build_record_learning_draft(candidate)
    draft = out["draft"]
    # No concrete action -> humanized pattern-name task.
    assert "orchestration contract update" in draft["task"]
    # Underscore pattern still hits the normalized tag table.
    assert draft["tags"] == ["orchestration", "contract"]


def test_stub_recommended_action_is_not_treated_as_concrete():
    engine = _load_engine()
    candidate = {"pattern_name": "learn-inbox", "summary": "x", "recommended_action": "review"}
    draft = engine.build_record_learning_draft(candidate)["draft"]
    assert draft["task"].startswith("Apply the 'learn inbox' pattern")


def test_evidence_present_validation_still_manual():
    engine = _load_engine()
    candidate = {
        "pattern_name": "learn-inbox",
        "summary": "Inbox candidates must be reviewed before promotion.",
        "evidence": ["inbox.jsonl row 3", "lessons.jsonl unchanged"],
    }
    draft = engine.build_record_learning_draft(candidate)["draft"]
    assert draft["validation"].startswith("MANUAL VALIDATION REQUIRED")
    # Evidence is surfaced for the reviewer but never asserted as truth.
    assert "inbox.jsonl row 3" in draft["validation"]


def test_no_evidence_validation_is_manual_marker_only():
    engine = _load_engine()
    candidate = {"pattern_name": "anything", "summary": "Some lesson.", "evidence": []}
    draft = engine.build_record_learning_draft(candidate)["draft"]
    assert draft["validation"] == "MANUAL VALIDATION REQUIRED: confirm evidence before promotion."


def test_unknown_pattern_gets_fallback_tags():
    engine = _load_engine()
    candidate = {"pattern_name": "totally_new_thing", "summary": "A lesson."}
    draft = engine.build_record_learning_draft(candidate)["draft"]
    assert draft["tags"] == ["learn"]


def test_local_summary_is_generalized_gently():
    engine = _load_engine()
    candidate = {
        "pattern_name": "some_pattern",
        "summary": "In commit ef24cc0a1b2c the post-commit hook queued candidates.",
        "evidence": ["scripts/post_commit_learn.py"],
    }
    draft = engine.build_record_learning_draft(candidate)["draft"]
    lesson = draft["lesson"]
    # The local "commit <sha>" reference is lifted out, meaning is preserved.
    # ("post-commit hook" is a real term and must survive.)
    assert "ef24cc0" not in lesson
    assert "commit ef24cc0" not in lesson.lower()
    assert lesson.startswith("The post-commit hook queued candidates")
    assert lesson[0].isupper()


def test_generalize_is_idempotent():
    engine = _load_engine()
    once = engine._draft_generalize_lesson("In commit abc1234 a thing happened.")
    twice = engine._draft_generalize_lesson(once)
    assert once == twice


def test_missing_summary_yields_pending_lesson():
    engine = _load_engine()
    draft = engine.build_record_learning_draft({"pattern_name": "p"})["draft"]
    assert "pending review" in draft["lesson"].lower()


def test_non_dict_candidate_rejected():
    engine = _load_engine()
    import pytest

    with pytest.raises(ValueError):
        engine.build_record_learning_draft(["not", "a", "dict"])


# --- preview_inbox_candidate: selection + no-write guarantee -------------------


def _rows():
    return [
        {"status": "pending", "commit": "abc123def456", "pattern_name": "release-gate-v2",
         "summary": "Release gate must run before tagging.", "confidence": "high",
         "evidence": ["scripts/release-check.sh"],
         "recommended_action": "Run the release gate before every tag"},
        {"status": "pending", "commit": "fff999000111", "pattern_name": "learn-inbox",
         "summary": "Review inbox candidates before promotion.", "confidence": "medium",
         "evidence": []},
    ]


def test_preview_selects_one_and_returns_draft(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, _rows())
    result = engine.preview_inbox_candidate(tmp_path, pattern_name="release-gate-v2")
    assert result["status"] == "ok"
    assert result["candidate"] == "release-gate-v2"
    assert result["write_performed"] is False
    assert result["draft"]["task"] == "Run the release gate before every tag"


def test_preview_does_not_write_inbox_or_lessons(tmp_path):
    engine = _load_engine()
    inbox = _seed_inbox(engine, tmp_path, _rows())
    lessons = engine.learning_store_path(tmp_path)
    lessons.parent.mkdir(parents=True, exist_ok=True)
    lessons.write_text('{"id":"keep"}\n', encoding="utf-8")
    inbox_before = inbox.read_text()

    engine.preview_inbox_candidate(tmp_path, commit="abc123d")

    assert inbox.read_text() == inbox_before
    assert lessons.read_text() == '{"id":"keep"}\n'


def test_preview_no_selector_aborts(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, _rows())
    assert engine.preview_inbox_candidate(tmp_path)["status"] == "no-selector"


def test_preview_no_match(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, _rows())
    assert engine.preview_inbox_candidate(tmp_path, pattern_name="nope")["status"] == "no-match"


def test_preview_ambiguous_refuses(tmp_path):
    engine = _load_engine()
    rows = _rows()
    rows.append({"status": "pending", "commit": "abc123def456",
                 "pattern_name": "dup", "summary": "y", "confidence": "low"})
    _seed_inbox(engine, tmp_path, rows)
    result = engine.preview_inbox_candidate(tmp_path, commit="abc123def456")
    assert result["status"] == "ambiguous"
    assert result["matched"] == 2


def test_preview_empty_inbox(tmp_path):
    engine = _load_engine()
    assert engine.preview_inbox_candidate(tmp_path, pattern_name="x")["status"] == "empty"
