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


def _rows():
    return [
        {"status": "pending", "commit": "abc123def456", "pattern_name": "release-gate-v2",
         "confidence": "high", "captured_at": "2026-06-16T00:13:46"},
        {"status": "pending", "commit": "fff999000111", "pattern_name": "learn-inbox",
         "confidence": "medium", "captured_at": "2026-06-16T00:13:59"},
    ]


def test_preview_does_not_write(tmp_path):
    engine = _load_engine()
    path = _seed_inbox(engine, tmp_path, _rows())

    result = engine.drop_inbox_candidate(tmp_path, pattern_name="release-gate-v2")
    assert result["status"] == "preview"
    assert result["matched"] == 1
    assert result["removed"]["pattern_name"] == "release-gate-v2"
    # File is unchanged on a dry run.
    assert len(path.read_text().splitlines()) == 2


def test_apply_removes_exactly_one(tmp_path):
    engine = _load_engine()
    path = _seed_inbox(engine, tmp_path, _rows())

    result = engine.drop_inbox_candidate(tmp_path, pattern_name="release-gate-v2", apply=True)
    assert result["status"] == "ok"
    assert result["remaining"] == 1
    remaining = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(remaining) == 1
    assert remaining[0]["pattern_name"] == "learn-inbox"


def test_commit_prefix_match(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, _rows())

    # Full SHA on the row is "abc123def456"; a short prefix still selects it.
    result = engine.drop_inbox_candidate(tmp_path, commit="abc123d", apply=True)
    assert result["status"] == "ok"
    assert result["removed"]["pattern_name"] == "release-gate-v2"


def test_no_selector_aborts(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, _rows())

    result = engine.drop_inbox_candidate(tmp_path)
    assert result["status"] == "no-selector"


def test_no_match_aborts_without_write(tmp_path):
    engine = _load_engine()
    path = _seed_inbox(engine, tmp_path, _rows())

    result = engine.drop_inbox_candidate(tmp_path, pattern_name="nope", apply=True)
    assert result["status"] == "no-match"
    assert len(path.read_text().splitlines()) == 2


def test_ambiguous_match_refuses(tmp_path):
    engine = _load_engine()
    rows = _rows()
    rows.append({"status": "pending", "commit": "abc123def456",
                 "pattern_name": "duplicate-sha", "confidence": "low"})
    path = _seed_inbox(engine, tmp_path, rows)

    # Two rows share the abc123... commit -> must refuse, no write.
    result = engine.drop_inbox_candidate(tmp_path, commit="abc123def456", apply=True)
    assert result["status"] == "ambiguous"
    assert result["matched"] == 2
    assert len(path.read_text().splitlines()) == 3


def test_never_touches_lessons_store(tmp_path):
    engine = _load_engine()
    _seed_inbox(engine, tmp_path, _rows())
    lessons = engine.learning_store_path(tmp_path)
    lessons.parent.mkdir(parents=True, exist_ok=True)
    lessons.write_text('{"id":"keep"}\n', encoding="utf-8")

    engine.drop_inbox_candidate(tmp_path, pattern_name="release-gate-v2", apply=True)
    assert lessons.read_text() == '{"id":"keep"}\n'
