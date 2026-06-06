import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "mq-mcp"


def load_release_gate_module(name: str):
    import importlib
    import sys

    sys.path.insert(0, str(APP_DIR))
    return importlib.import_module(f"release_gate.{name}")


def write_repo(tmp_path: Path, version: str = "1.4.0") -> Path:
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "VERSION").write_text(version, encoding="utf-8")
    (repo / "README.md").write_text(f"# sample\n\nCurrent: v{version}\n", encoding="utf-8")
    (repo / "ROADMAP.md").write_text(f"# Roadmap\n\nNext: v{version}\n", encoding="utf-8")
    (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [v{version}]\n", encoding="utf-8")
    docs = repo / "docs"
    docs.mkdir()
    (docs / "tool_contracts.json").write_text(
        json.dumps({"tools": [{"name": "read_repo_file", "class": "A"}]}),
        encoding="utf-8",
    )
    return repo


def test_release_gate_can_return_pass(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "pass"
    assert result.blockers == []
    assert any(check.name == "learn_hygiene_pass" and check.status == "pass" for check in result.checks)
    assert result.to_dict()["repo"] == "sample"


def test_release_gate_can_return_warning(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)

    result = runner.run_release_gate(repo, "v1.4.0")

    assert result.status == "warning"
    assert any("Tests were not run" in warning for warning in result.warnings)


def test_release_gate_can_return_blocked(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    (repo / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "blocked"
    assert any("CHANGELOG.md" in blocker for blocker in result.blockers)


def test_release_gate_blocks_unsafe_learn_hygiene(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    learn_store = repo / "learn_engine" / "memory" / "lessons.jsonl"
    learn_store.parent.mkdir(parents=True)
    learn_store.write_text(
        json.dumps(
            {
                "id": "learn_low",
                "repo": "sample",
                "source": "review",
                "task": "Low confidence",
                "lesson": "Low-confidence Ollama records should not be stored.",
                "validation": ["checked"],
                "risk": "unknown",
                "tags": ["ollama-learn", "low"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "blocked"
    assert any("Learn hygiene blocked" in blocker for blocker in result.blockers)
    assert any(check.name == "learn_hygiene_pass" and check.status == "blocked" for check in result.checks)


def test_release_gate_render_includes_operator_sections(tmp_path):
    runner = load_release_gate_module("runner")
    render = load_release_gate_module("render")
    repo = write_repo(tmp_path)

    output = render.render_release_gate(runner.run_release_gate(repo, "v1.4.0"))

    assert "MQ RELEASE GATE V2" in output
    assert "Blockers:" in output
    assert "Warnings:" in output
    assert "Next actions:" in output
