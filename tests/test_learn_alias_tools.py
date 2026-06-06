import ast
import importlib.util
import json
import sys
import types
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


def test_learn_aliases_delegate_to_canonical_tools(monkeypatch):
    server = _load_server_with_stubbed_dependencies()

    monkeypatch.setattr(server, "learning_status", lambda repo="": f"status:{repo}")
    monkeypatch.setattr(server, "search_learnings", lambda query, repo="": f"search:{query}:{repo}")
    monkeypatch.setattr(server, "get_learning", lambda learning_id: f"get:{learning_id}")

    assert server.learn_status(repo="mq-agent") == "status:mq-agent"
    assert server.search_learned_patterns(query="release", repo="mq-agent") == "search:release:mq-agent"
    assert server.explain_learned_pattern(id="learn_123") == "get:learn_123"


def _load_server_with_stubbed_dependencies():
    class FakeMCP:
        def __init__(self, *args, **kwargs):
            pass

        def custom_route(self, *args, **kwargs):
            return lambda func: func

        def tool(self, *args, **kwargs):
            return lambda func: func

    modules = {
        "requests": types.SimpleNamespace(),
        "psutil": types.SimpleNamespace(cpu_percent=lambda interval=0: 0, virtual_memory=lambda: types.SimpleNamespace(percent=0)),
        "pandas": types.SimpleNamespace(read_csv=lambda path: None),
        "guitarpro": types.SimpleNamespace(parse=lambda path: None),
        "PIL": types.ModuleType("PIL"),
        "PIL.Image": types.SimpleNamespace(open=lambda path: None),
        "mcp": types.ModuleType("mcp"),
        "mcp.server": types.ModuleType("mcp.server"),
        "mcp.server.fastmcp": types.SimpleNamespace(FastMCP=FakeMCP),
        "starlette": types.ModuleType("starlette"),
        "starlette.requests": types.SimpleNamespace(Request=object),
        "starlette.responses": types.SimpleNamespace(JSONResponse=dict),
    }
    for name, module in modules.items():
        sys.modules.setdefault(name, module)

    spec = importlib.util.spec_from_file_location("mq_mcp_server_alias_test", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
