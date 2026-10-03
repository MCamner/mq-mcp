import json
from pathlib import Path


def test_read_only_client_profiles_exclude_shadow_writes():
    root = Path(__file__).resolve().parents[1]
    contracts = {t["name"]: t for t in json.loads((root / "docs/tool_contracts.json").read_text())["tools"]}
    for name in ("codex", "claude-desktop"):
        profile = json.loads((root / "profiles" / f"{name}.json").read_text())
        for tool in profile["recommended_tools"]:
            assert contracts[tool]["class"] in ("A", "B"), (name, tool)
