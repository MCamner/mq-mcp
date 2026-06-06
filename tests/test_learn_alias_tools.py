import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
CONTRACTS_PATH = ROOT / "docs" / "tool_contracts.json"


def _mcp_tool_names() -> set[str]:
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
            ):
                names.add(node.name)
    return names


def test_mq_agent_learn_alias_tools_exist():
    names = _mcp_tool_names()

    assert "learn_status" in names
    assert "search_learned_patterns" in names
    assert "explain_learned_pattern" in names


def test_learn_alias_tools_are_class_a_contracts():
    data = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    contracts = {item["name"]: item for item in data["tools"]}

    for name in ("learn_status", "search_learned_patterns", "explain_learned_pattern"):
        assert contracts[name]["class"] == "A"
        assert contracts[name]["write"] is False
        assert contracts[name]["subprocess"] is False
