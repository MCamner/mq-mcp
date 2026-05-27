import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "mq-mcp" / "main.py"


def load_cli():
    spec = importlib.util.spec_from_file_location("mq_mcp_cli", CLI_PATH)
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
    assert payload["version"] == "1.1.0"
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
    assert payload["version"] == "1.1.0"
    assert payload["status"] == "ok"
    assert payload["tool_count"] == 61
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
    assert payload["version"] == "1.1.0"
