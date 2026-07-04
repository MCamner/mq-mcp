import importlib.util
import json
from pathlib import Path


def _load_script():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "export_learn_to_obsidian.py"
    spec = importlib.util.spec_from_file_location("export_learn_to_obsidian", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_lessons(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _row(**over):
    base = {
        "id": "learn_20260603_002331_0001",
        "repo": "mq-mcp",
        "risk": "low",
        "source": "manual",
        "created_at": "2026-06-03T00:23:31Z",
        "lesson": "Sync version and proof docs in the same pass.",
        "task": "Sync roadmap release status with version",
        "problem": "VERSION lagged ROADMAP.",
        "solution": "Run a release-docs consistency check before commit.",
        "validation": ["Updated VERSION", "Ran pytest"],
        "tags": ["docs", "release"],
        "commands_used": ["uv run pytest -q"],
        "files_touched": ["VERSION", "README.md"],
    }
    base.update(over)
    return base


# --- load & normalize --------------------------------------------------------


def test_load_skips_blank_and_collects_bad_json(tmp_path):
    eng = _load_script()
    p = tmp_path / "lessons.jsonl"
    p.write_text('{"id":"a"}\n\n  \nnot json\n{"id":"b"}\n', encoding="utf-8")
    lessons, errors = eng.load_lessons(p)
    assert [l["id"] for l in lessons] == ["a", "b"]
    assert len(errors) == 1 and "invalid JSON" in errors[0]


def test_load_missing_file_is_reported_not_raised(tmp_path):
    eng = _load_script()
    lessons, errors = eng.load_lessons(tmp_path / "nope.jsonl")
    assert lessons == []
    assert any("not found" in e for e in errors)


def test_normalize_validation_list_is_preserved():
    eng = _load_script()
    out = eng.normalize_lesson(_row())
    assert out["validation"] == ["Updated VERSION", "Ran pytest"]


def test_normalize_validation_string_is_wrapped():
    eng = _load_script()
    out = eng.normalize_lesson(_row(validation="single line"))
    assert out["validation"] == ["single line"]


def test_normalize_fallbacks_for_missing_fields():
    eng = _load_script()
    out = eng.normalize_lesson({"id": "x"})
    assert out["repo"] == "unknown"
    assert out["risk"] == "unknown"
    assert out["tags"] == ["learn"]
    assert out["validation"] == []
    assert out["lesson"] == "No lesson text stored."


def test_normalize_does_not_invent_pattern_type():
    eng = _load_script()
    out = eng.normalize_lesson(_row())
    assert "pattern_type" not in out


# --- rendering ---------------------------------------------------------------


def test_render_has_frontmatter_and_sections(tmp_path):
    eng = _load_script()
    md = eng.render_lesson_markdown(eng.normalize_lesson(_row()), tmp_path)
    assert md.startswith("---\n")
    assert "id: learn_20260603_002331_0001" in md
    assert "approved: true" in md
    assert "hot_candidate: false" in md
    assert "## Lesson" in md and "## Task" in md and "## Validation" in md
    assert "- Updated VERSION" in md  # validation rendered as bullets
    assert "pattern_type" not in md


def test_render_links_repo_and_tags_but_not_missing_system(tmp_path):
    eng = _load_script()
    # No systems/mq-mcp/index.md exists under tmp vault -> system backlink omitted.
    md = eng.render_lesson_markdown(eng.normalize_lesson(_row()), tmp_path)
    assert "[[memory/learn/repos/mq-mcp]]" in md
    assert "[[memory/learn/tags/docs]]" in md
    assert "[[systems/mq-mcp/index]]" not in md


def test_render_includes_system_backlink_when_present(tmp_path):
    eng = _load_script()
    sys_idx = tmp_path / "systems" / "mq-mcp" / "index.md"
    sys_idx.parent.mkdir(parents=True, exist_ok=True)
    sys_idx.write_text("# mq-mcp\n", encoding="utf-8")
    md = eng.render_lesson_markdown(eng.normalize_lesson(_row()), tmp_path)
    assert "[[systems/mq-mcp/index]]" in md


def test_no_validation_renders_placeholder(tmp_path):
    eng = _load_script()
    md = eng.render_lesson_markdown(eng.normalize_lesson(_row(validation=[])), tmp_path)
    assert "No validation text stored." in md


# --- export orchestration & idempotency -------------------------------------


def test_export_writes_expected_tree(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [
        _row(),
        _row(id="learn_20260604_010101_0002", repo="mq-agent", tags=["mq-agent", "release"],
             created_at="2026-06-04T01:01:01Z"),
    ])
    report = eng.export_lessons(tmp_path / "vault", lessons)
    learn = tmp_path / "vault" / "memory" / "learn"
    assert (learn / "patterns" / "learn_20260603_002331_0001.md").exists()
    assert (learn / "patterns" / "learn_20260604_010101_0002.md").exists()
    assert (learn / "repos" / "mq-mcp.md").exists()
    assert (learn / "repos" / "mq-agent.md").exists()
    assert (learn / "tags" / "release.md").exists()  # shared tag across both
    assert (learn / "index.md").exists()
    assert report["lessons_exported"] == 2
    assert report["pattern_files_created"] == 2
    assert report["errors"] == []


def test_shared_tag_lists_both_lessons(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [
        _row(id="a1", tags=["release"]),
        _row(id="a2", tags=["release"]),
    ])
    eng.export_lessons(tmp_path / "vault", lessons)
    body = (tmp_path / "vault" / "memory" / "learn" / "tags" / "release.md").read_text()
    assert "[[memory/learn/patterns/a1]]" in body
    assert "[[memory/learn/patterns/a2]]" in body


def test_second_run_is_idempotent(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [_row()])
    eng.export_lessons(tmp_path / "vault", lessons)
    report2 = eng.export_lessons(tmp_path / "vault", lessons)
    assert report2["pattern_files_created"] == 0
    assert report2["pattern_files_updated"] == 0
    assert report2["pattern_files_unchanged"] == 1
    assert report2["repo_indexes_written"] == 0
    assert report2["tag_indexes_written"] == 0
    assert report2["index_written"] is False


def test_changed_lesson_updates_only_that_file(tmp_path):
    eng = _load_script()
    p = _seed_lessons(tmp_path / "lessons.jsonl", [_row()])
    eng.export_lessons(tmp_path / "vault", p)
    _seed_lessons(p, [_row(lesson="A revised lesson body.")])
    report = eng.export_lessons(tmp_path / "vault", p)
    assert report["pattern_files_updated"] == 1
    assert report["pattern_files_created"] == 0
    note = (tmp_path / "vault" / "memory" / "learn" / "patterns"
            / "learn_20260603_002331_0001.md").read_text()
    assert "A revised lesson body." in note


def test_dry_run_writes_nothing(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [_row()])
    report = eng.export_lessons(tmp_path / "vault", lessons, dry_run=True)
    assert report["dry_run"] is True
    assert report["pattern_files_created"] == 1  # would-create is reported
    assert not (tmp_path / "vault").exists()  # but nothing is on disk


def test_record_without_id_is_skipped(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [_row(), {"repo": "x", "lesson": "y"}])
    report = eng.export_lessons(tmp_path / "vault", lessons)
    assert report["lessons_read"] == 2
    assert report["lessons_exported"] == 1
    assert any("no id" in e for e in report["errors"])


def test_unsafe_tag_slug_is_filesystem_safe(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [_row(tags=["v0.6.0", "SKILLS.md"])])
    eng.export_lessons(tmp_path / "vault", lessons)
    tags_dir = tmp_path / "vault" / "memory" / "learn" / "tags"
    names = sorted(p.name for p in tags_dir.iterdir())
    assert names == ["skills-md.md", "v0-6-0.md"]


def test_case_variant_tags_merge_into_one_page(tmp_path):
    eng = _load_script()
    # "MD004" and "md004" are the same tag with inconsistent casing; on a
    # case-insensitive filesystem they MUST resolve to one page with both lessons,
    # and the reported tag count MUST equal the number of files written.
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [
        _row(id="a1", tags=["MD004"]),
        _row(id="a2", tags=["md004"]),
    ])
    report = eng.export_lessons(tmp_path / "vault", lessons)
    tags_dir = tmp_path / "vault" / "memory" / "learn" / "tags"
    files = list(tags_dir.iterdir())
    assert [f.name for f in files] == ["md004.md"]
    assert report["tag_indexes_written"] == len(files) == 1
    body = files[0].read_text()
    assert "[[memory/learn/patterns/a1]]" in body
    assert "[[memory/learn/patterns/a2]]" in body


def test_same_lesson_with_case_variant_tags_counted_once(tmp_path):
    eng = _load_script()
    lessons = _seed_lessons(tmp_path / "lessons.jsonl", [_row(id="a1", tags=["MD004", "md004"])])
    eng.export_lessons(tmp_path / "vault", lessons)
    body = (tmp_path / "vault" / "memory" / "learn" / "tags" / "md004.md").read_text()
    assert body.count("[[memory/learn/patterns/a1]]") == 1
    assert "1 lesson(s)" in body
