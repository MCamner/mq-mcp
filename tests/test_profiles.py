import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"


def test_expected_profiles_exist():
    names = {path.stem for path in PROFILES.glob("*.json")}

    assert {
        "claude-desktop",
        "codex",
        "developer",
        "local-macos",
        "mq-agent",
        "openai-bridge",
        "read-only",
        "repo-only",
    } <= names


def test_profiles_have_required_contract():
    for path in PROFILES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["schema_version"] == "mq-mcp.profile.v1"
        assert data["name"] == path.stem
        assert data["command"]
        assert data["args"]
        assert isinstance(data["env"], dict)
        assert data["recommended_tools"]
        assert data["safety_notes"]


def test_read_only_client_profiles_recommend_only_class_a_b_tools():
    contracts = {
        tool["name"]: tool
        for tool in json.loads((ROOT / "docs" / "tool_contracts.json").read_text(encoding="utf-8"))["tools"]
    }
    for name in ("codex", "claude-desktop"):
        data = json.loads((PROFILES / f"{name}.json").read_text(encoding="utf-8"))
        for tool in data["recommended_tools"]:
            assert contracts[tool]["class"] in ("A", "B"), (name, tool)
