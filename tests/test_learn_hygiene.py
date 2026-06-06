import json
from pathlib import Path


def _load_engine():
    import importlib.util
    import sys

    module_path = Path(__file__).resolve().parents[1] / "mq-mcp" / "learn_engine.py"
    spec = importlib.util.spec_from_file_location("learn_engine_hygiene_test", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["learn_engine_hygiene_test"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _append_raw_record(engine, repo_root: Path, record: dict):
    path = engine.learning_store_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def test_learn_hygiene_empty_store_passes(tmp_path):
    engine = _load_engine()

    report = engine.hygiene_report(tmp_path)

    assert report["status"] == "pass"
    assert report["records"] == 0
    assert report["duplicates"] == []


def test_learn_hygiene_detects_duplicates(tmp_path):
    engine = _load_engine()
    record1 = engine.make_learning(
        tmp_path,
        repo="mq-mcp",
        source="manual",
        task="Fix docs drift",
        lesson="Keep README and contracts synced.",
        validation="tested",
        risk="low",
    ).to_dict()
    record2 = {**record1, "id": "learn_duplicate"}

    _append_raw_record(engine, tmp_path, record1)
    _append_raw_record(engine, tmp_path, record2)

    report = engine.hygiene_report(tmp_path)

    assert report["status"] == "warning"
    assert report["duplicates"] == ["learn_duplicate"]


def test_learn_hygiene_blocks_invalid_and_low_confidence_storage(tmp_path):
    engine = _load_engine()
    invalid = {
        "id": "bad",
        "repo": "",
        "source": "manual",
        "task": "Bad record",
        "lesson": "Missing repo should be invalid.",
        "validation": ["checked"],
        "risk": "low",
        "tags": [],
    }
    low_confidence = engine.make_learning(
        tmp_path,
        repo="mq-mcp",
        source="review",
        task="Low confidence candidate",
        lesson="Low-confidence Ollama records should not be stored.",
        validation="contract check",
        tags=["ollama-learn", "low"],
        risk="unknown",
    ).to_dict()

    _append_raw_record(engine, tmp_path, invalid)
    _append_raw_record(engine, tmp_path, low_confidence)

    report = engine.hygiene_report(tmp_path)

    assert report["status"] == "blocked"
    assert report["invalid_records"] == ["bad"]
    assert report["low_confidence_stored"] == [low_confidence["id"]]
