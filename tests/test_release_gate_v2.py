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
        json.dumps({
            "tools": [
                {"name": "read_repo_file", "class": "A", "write": False},
                {"name": "learn_status", "class": "A", "write": False},
                {"name": "search_learned_patterns", "class": "A", "write": False},
                {"name": "explain_learned_pattern", "class": "A", "write": False},
            ]
        }),
        encoding="utf-8",
    )
    (docs / "LEARNING_CONTRACT.md").write_text("# Learning Contract\n", encoding="utf-8")
    (docs / "LEARNING_MODEL.md").write_text("# Learning Model\n", encoding="utf-8")
    schemas = repo / "schemas"
    schemas.mkdir()
    (schemas / "learning.schema.json").write_text(
        json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}),
        encoding="utf-8",
    )
    package = repo / "mq-mcp"
    package.mkdir()
    (package / "server.py").write_text(
        "def learn_status(): pass\n"
        "def search_learned_patterns(): pass\n"
        "def explain_learned_pattern(): pass\n",
        encoding="utf-8",
    )
    write_repo_signal_export(repo)
    return repo


def write_repo_signal_export(repo: Path) -> Path:
    exports = repo / ".repo-signal" / "exports"
    exports.mkdir(parents=True)
    for filename, schema in {
        "callgraph.json": "callgraph.v1",
        "symbol_index.json": "symbol_index.v1",
        "repo_summary.json": "repo_summary.v1",
        "risk_map.json": "risk_map.v1",
    }.items():
        (exports / filename).write_text(json.dumps({"schema": schema}), encoding="utf-8")
    return exports


def test_release_gate_can_return_pass(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "pass"
    assert result.blockers == []
    assert any(check.name == "learn_contract_valid" and check.status == "pass" for check in result.checks)
    assert any(check.name == "learn_alias_tools_present" and check.status == "pass" for check in result.checks)
    assert any(check.name == "learn_hygiene_pass" and check.status == "pass" for check in result.checks)
    assert any(check.name == "repo_signal_readiness_export" and check.status == "pass" for check in result.checks)
    assert result.to_dict()["repo"] == "sample"


def test_release_gate_can_return_warning(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)

    result = runner.run_release_gate(repo, "v1.4.0")

    assert result.status == "warning"
    assert any("Tests were not run" in warning for warning in result.warnings)


def test_non_mcp_repo_without_tool_contracts_does_not_fail_safety_checks(tmp_path):
    checks = load_release_gate_module("checks")
    repo = tmp_path / "plain-repo"
    repo.mkdir()

    contracts = checks.check_contracts_valid(repo)
    safety = checks.check_safety_classes_valid(repo)
    learn_contract = checks.check_learn_contract_valid(repo)
    learn_aliases = checks.check_learn_alias_tools_present(repo)

    assert contracts.status == "warning"
    assert contracts.blocker is False
    assert "non-MCP repo" in contracts.message
    assert safety.status == "pass"
    assert "No MCP server detected" in safety.message
    assert learn_contract.status == "pass"
    assert "No mq-mcp server detected" in learn_contract.message
    assert learn_aliases.status == "pass"
    assert "No mq-mcp server detected" in learn_aliases.message


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


def test_release_gate_blocks_invalid_learn_contract(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    (repo / "schemas" / "learning.schema.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "blocked"
    assert any("Learning schema missing keys" in blocker for blocker in result.blockers)
    assert any(check.name == "learn_contract_valid" and check.status == "blocked" for check in result.checks)


def test_release_gate_blocks_missing_learn_alias_tools(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    (repo / "mq-mcp" / "server.py").write_text("def learn_status(): pass\n", encoding="utf-8")

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "blocked"
    assert any("Learn alias tools are not release-ready" in blocker for blocker in result.blockers)
    assert any(check.name == "learn_alias_tools_present" and check.status == "blocked" for check in result.checks)


def test_release_gate_validates_perception_artifacts(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    fixture = repo / "tests" / "fixtures" / "sample_perception_output.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        json.dumps(
            {
                "source_type": "screenshot",
                "source_path": "docs/screenshot.png",
                "ocr_text": "Release ready",
                "visual_summary": "Release status screenshot.",
                "detected_regions": [],
                "risk_signals": [],
                "confidence": "medium",
            }
        ),
        encoding="utf-8",
    )

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "pass"
    assert any(
        check.name == "perception_artifacts_valid" and check.status == "pass"
        for check in result.checks
    )


def test_release_gate_blocks_invalid_perception_artifacts(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    fixture = repo / "tests" / "fixtures" / "sample_perception_output.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        json.dumps(
            {
                "source_type": "screenshot",
                "source_path": "docs/screenshot.png",
                "ocr_text": "Release ready",
                "visual_summary": "Release status screenshot.",
                "risk_signals": "low contrast",
                "confidence": "medium",
            }
        ),
        encoding="utf-8",
    )

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "blocked"
    assert any("Invalid perception artifact" in blocker for blocker in result.blockers)
    assert any(
        check.name == "perception_artifacts_valid" and check.status == "blocked"
        for check in result.checks
    )


def test_release_gate_blocks_invalid_repo_signal_export(tmp_path):
    runner = load_release_gate_module("runner")
    repo = write_repo(tmp_path)
    export = repo / ".repo-signal" / "exports" / "repo_summary.json"
    export.write_text(json.dumps({"schema": "repo_summary.v0"}), encoding="utf-8")

    result = runner.run_release_gate(repo, "v1.4.0", test_command=["true"])

    assert result.status == "blocked"
    assert any("Invalid repo-signal readiness export" in blocker for blocker in result.blockers)
    assert any(
        check.name == "repo_signal_readiness_export" and check.status == "blocked"
        for check in result.checks
    )


def test_release_gate_render_includes_operator_sections(tmp_path):
    runner = load_release_gate_module("runner")
    render = load_release_gate_module("render")
    repo = write_repo(tmp_path)

    output = render.render_release_gate(runner.run_release_gate(repo, "v1.4.0"))

    assert "MQ RELEASE GATE V2" in output
    assert "Blockers:" in output
    assert "Warnings:" in output
    assert "Next actions:" in output
