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


ROW_A = {
    "status": "pending",
    "source": "post-commit",
    "commit": "aaaaaaaaaaaa",
    "captured_at": "2026-10-01T10:00:00",
    "pattern_name": "release-gate-v2",
    "confidence": "high",
    "summary": "Run the release gate before tagging.",
    "evidence": ["scripts/release-check.sh"],
    "recommended_action": "Run the release gate before every version tag",
}
ROW_B = {**ROW_A, "commit": "bbbbbbbbbbbb", "summary": "Another lesson."}


def _extraction(confidence="medium", reason="explicit approval required", status="dry_run"):
    return {
        "status": status,
        "stored": False,
        "reason": reason,
        "file": "mq_agent/main.py",
        "record": {
            "pattern_name": "schema-force-include",
            "pattern_type": "release",
            "summary": "Schemas read at runtime must be force-included in the wheel.",
            "evidence": ["pyproject.toml"],
            "recommended_action": "Force-include every runtime schema in pyproject.toml",
            "confidence": confidence,
            "should_store": False,
        },
    }


# --- candidate_id: stable, content-derived ------------------------------------


def test_candidate_id_is_stable_and_prefixed():
    engine = _load_engine()
    first = engine.inbox_candidate_id(dict(ROW_A))
    assert first.startswith("cand-")
    assert first == engine.inbox_candidate_id(json.loads(json.dumps(ROW_A)))
    assert first != engine.inbox_candidate_id(ROW_B)


def test_legacy_rows_without_stored_id_are_addressable(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, [ROW_A, ROW_B])
    target = engine.inbox_candidate_id(ROW_B)
    out = engine.draft_inbox_candidate(tmp_path, candidate_id=target)
    assert out["status"] == "ok"
    assert out["candidate_id"] == target
    assert out["draft"]["lesson"] == "Another lesson."


def test_candidate_id_is_exact_not_prefix(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, [ROW_A])
    cid = engine.inbox_candidate_id(ROW_A)
    assert engine.draft_inbox_candidate(tmp_path, candidate_id=cid[:-2])["status"] == "no-match"


def test_drop_by_candidate_id_removes_only_that_row(tmp_path):
    engine = _load_engine()
    path = _seed_inbox(engine, tmp_path, [ROW_A, ROW_B])
    cid = engine.inbox_candidate_id(ROW_A)
    out = engine.drop_inbox_candidate(tmp_path, candidate_id=cid, apply=True)
    assert out["status"] == "ok"
    remaining = [json.loads(line) for line in path.read_text().splitlines()]
    assert remaining == [ROW_B]


def test_no_selector_still_aborts(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, [ROW_A])
    assert engine.draft_inbox_candidate(tmp_path)["status"] == "no-selector"
    assert engine.drop_inbox_candidate(tmp_path, apply=True)["status"] == "no-selector"


# --- queue_review_candidate: explicit operator queueing -----------------------


def test_queue_writes_pending_row_and_returns_its_id(tmp_path):
    engine = _load_engine()
    out = engine.queue_review_candidate(tmp_path, _extraction(), repo="mq-agent")
    assert out["status"] == "queued"
    rows = engine.load_inbox(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending"
    assert row["source"] == "review"
    assert row["file"] == "mq_agent/main.py"
    assert row["repo"] == "mq-agent"
    assert out["candidate_id"] == engine.inbox_candidate_id(row)
    # Never the curated store.
    assert not engine.learning_store_path(tmp_path).exists()


def test_queued_candidate_drafts_for_its_own_repo(tmp_path):
    engine = _load_engine()
    cid = engine.queue_review_candidate(tmp_path, _extraction(), repo="mq-agent")["candidate_id"]
    draft = engine.draft_inbox_candidate(tmp_path, candidate_id=cid)["draft"]
    assert draft["repo"] == "mq-agent"
    assert draft["validation"].startswith("MANUAL VALIDATION REQUIRED")


def test_queue_refuses_low_confidence(tmp_path):
    engine = _load_engine()
    out = engine.queue_review_candidate(tmp_path, _extraction(confidence="low"), repo="mq-agent")
    assert out["status"] == "not-queued"
    assert engine.load_inbox(tmp_path) == []


def test_queue_refuses_missing_repo_context_placeholder(tmp_path):
    engine = _load_engine()
    refusal = _extraction(reason="verified repo_context required")
    out = engine.queue_review_candidate(tmp_path, refusal, repo="mq-agent")
    assert out["status"] == "not-queued"
    assert engine.load_inbox(tmp_path) == []


def test_queue_refuses_unavailable_and_no_review(tmp_path):
    engine = _load_engine()
    for result in ({"status": "unavailable", "reason": "Ollama down"}, {"status": "no_review", "reason": "none"}):
        assert engine.queue_review_candidate(tmp_path, result, repo="mq-agent")["status"] == "not-queued"
    assert engine.load_inbox(tmp_path) == []


def test_queue_same_candidate_twice_returns_existing_id(tmp_path):
    engine = _load_engine()
    first = engine.queue_review_candidate(tmp_path, _extraction(), repo="mq-agent")
    second = engine.queue_review_candidate(tmp_path, _extraction(), repo="mq-agent")
    assert second["status"] == "duplicate"
    assert second["candidate_id"] == first["candidate_id"]
    assert len(engine.load_inbox(tmp_path)) == 1


# --- server tools: the ID round-trips queue -> inbox -> draft -> drop ----------


def test_tools_round_trip_one_candidate_id(tmp_path, monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq-mcp"))
    import server

    repo = tmp_path / "mq-mcp"
    repo.mkdir()
    monkeypatch.setattr(server, "REPO_ROOT", repo)
    monkeypatch.setattr(
        server, "_extract_from_last_review", lambda path, repo_path, tool: ("mq-agent", "", _extraction())
    )

    queued = json.loads(server.learn_queue_from_last_review("mq_agent/main.py"))
    cid = queued["candidate_id"]
    assert queued["status"] == "queued"

    assert cid in server.learn_inbox()
    draft = json.loads(server.learn_inbox_draft(candidate_id=cid))
    assert draft["candidate_id"] == cid
    assert draft["draft"]["repo"] == "mq-agent"

    assert "Dry run" in server.learn_inbox_drop(candidate_id=cid)
    assert "Removed 1 candidate" in server.learn_inbox_drop(candidate_id=cid, apply=True)
    assert "empty" in server.learn_inbox().lower()


def test_queue_tool_reports_allowlist_refusal_as_not_queued(tmp_path, monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq-mcp"))
    import server

    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    out = json.loads(server.learn_queue_from_last_review("x.py", repo_path="/definitely/not/allowed"))
    assert out["status"] == "not-queued"
    assert not (tmp_path / "learn_engine").exists()
