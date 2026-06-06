import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "mq-mcp" / "main.py"


def load_cli():
    spec = importlib.util.spec_from_file_location("mq_mcp_cli", CLI_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_read_version_matches_version_file():
    cli = load_cli()
    assert cli.read_version() == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_doctor_json_reports_required_status(capsys):
    cli = load_cli()
    result = cli.doctor(json_output=True)
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["name"] == "mq-mcp"
    assert payload["version"] == "1.10.0"
    assert payload["status"] == "ok"
    assert any(item["name"] == "validate_script" for item in payload["checks"])


def test_config_path_command_prints_env_path(capsys):
    cli = load_cli()
    result = cli.main(["config", "path"])

    assert result == 0
    assert capsys.readouterr().out.strip().endswith("mq-mcp/.env")


def test_health_json_reports_tool_count(capsys):
    cli = load_cli()
    result = cli.main(["health", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["version"] == "1.10.0"
    assert payload["status"] == "ok"
    assert payload["tool_count"] >= 100
    assert payload["contracts_ok"] is True


def test_report_redacts_secret_environment(monkeypatch):
    cli = load_cli()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    report = cli.build_report(run_validation=False)

    assert report["env"]["OPENAI_API_KEY"]["value"] == "<redacted>"
    assert "sk-test-secret" not in json.dumps(report)


def test_profiles_list_includes_expected_templates(capsys):
    cli = load_cli()
    result = cli.main(["profiles", "list"])
    output = capsys.readouterr().out

    assert result == 0
    assert "read-only" in output
    assert "claude-desktop" in output
    assert "mq-agent" in output


def test_profiles_show_returns_profile_json(capsys):
    cli = load_cli()
    result = cli.main(["profiles", "show", "read-only"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["schema_version"] == "mq-mcp.profile.v1"
    assert payload["name"] == "read-only"


def test_stability_show_returns_baseline_json(capsys):
    cli = load_cli()
    result = cli.main(["stability", "show"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["schema_version"] == "mq-mcp.stability.v1"
    assert payload["version"] == "1.10.0"


def test_release_gate_run_json_reports_status(capsys, tmp_path):
    cli = load_cli()
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "VERSION").write_text("1.4.0", encoding="utf-8")
    (repo / "README.md").write_text("Current v1.4.0", encoding="utf-8")
    (repo / "ROADMAP.md").write_text("Next v1.4.0", encoding="utf-8")
    (repo / "CHANGELOG.md").write_text("## [v1.4.0]", encoding="utf-8")
    docs = repo / "docs"
    docs.mkdir()
    (docs / "tool_contracts.json").write_text(
        json.dumps({"tools": [{"name": "read_repo_file", "class": "A"}]}),
        encoding="utf-8",
    )

    result = cli.main(["release-gate", "run", "--repo", str(repo), "--target", "v1.4.0", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["repo"] == "sample"
    assert payload["status"] == "warning"


def test_release_gate_run_cli_accepts_test_command(capsys, tmp_path):
    cli = load_cli()
    repo = tmp_path / "plain"
    repo.mkdir()
    (repo / "VERSION").write_text("1.4.0", encoding="utf-8")
    (repo / "README.md").write_text("Current v1.4.0", encoding="utf-8")
    (repo / "ROADMAP.md").write_text("Next v1.4.0", encoding="utf-8")
    (repo / "CHANGELOG.md").write_text("## [v1.4.0]", encoding="utf-8")

    result = cli.main([
        "release-gate",
        "run",
        "--repo",
        str(repo),
        "--target",
        "v1.4.0",
        "--test-command",
        "true",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["tests_pass"]["status"] == "pass"
