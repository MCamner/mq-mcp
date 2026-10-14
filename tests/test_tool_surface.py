"""mq-mcp.tool-surface.v1: the registered tools as a committed contract.

docs/tool_contracts.json says which class each tool has, but not what it
accepts; the parameters existed only in a running server's /tools. A consumer
(mq-agent's stack compatibility gate) could not check a call against them
without a live process, and a live process can lag main. This file publishes
names, classes and parameters from the in-process registry, and CI keeps it
current.
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "tool_surface.v1.schema.json"
SURFACE = ROOT / "contracts" / "tool_surface.v1.json"
CONTRACTS = ROOT / "docs" / "tool_contracts.json"

sys.path.insert(0, str(ROOT / "mq-mcp"))
_spec = importlib.util.spec_from_file_location(
    "export_tool_surface", ROOT / "scripts" / "export_tool_surface.py"
)
assert _spec and _spec.loader
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def surface() -> dict:
    return json.loads(SURFACE.read_text(encoding="utf-8"))


def _tool(**overrides) -> dict:
    tool = {
        "name": "read_repo_file",
        "safety_class": "A",
        "write": False,
        "subprocess": False,
        "parameters": [{"name": "relative_path", "type": ["string"], "required": True}],
        "signature_sha256": "0" * 64,
    }
    tool.update(overrides)
    return tool


def _doc(*tools: dict) -> dict:
    return {
        "schema": "mq-mcp.tool-surface.v1",
        "producer": "mq-mcp",
        "tool_count": len(tools),
        "tools": list(tools),
    }


# --- schema ---------------------------------------------------------------


def test_schema_accepts_a_minimal_surface(validator) -> None:
    assert list(validator.iter_errors(_doc(_tool()))) == []


@pytest.mark.parametrize(
    "bad",
    [
        _tool(safety_class="E"),
        _tool(safety_class="read-only"),
        {k: v for k, v in _tool().items() if k != "parameters"},
        _tool(extra=True),
        _tool(parameters=[{"name": "x", "type": ["string"], "required": True, "description": "d"}]),
        _tool(signature_sha256="abc"),
    ],
)
def test_schema_rejects_malformed_tools(validator, bad) -> None:
    assert list(validator.iter_errors(_doc(bad))) != []


# --- export rules ---------------------------------------------------------


def test_parameters_keep_name_type_and_required_only() -> None:
    schema = {
        "type": "object",
        "properties": {
            "repo_path": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            "max_files": {"type": "integer", "default": 5, "description": "cap"},
        },
        "required": ["max_files"],
    }

    assert export.parameters_from_input_schema(schema) == [
        {"name": "max_files", "type": ["integer"], "required": True},
        {"name": "repo_path", "type": ["null", "string"], "required": False},
    ]


def test_descriptions_do_not_change_the_signature() -> None:
    plain = {"properties": {"a": {"type": "string"}}, "required": ["a"]}
    described = {"properties": {"a": {"type": "string", "description": "new prose"}}, "required": ["a"]}

    assert export.signature(export.parameters_from_input_schema(plain)) == export.signature(
        export.parameters_from_input_schema(described)
    )


def test_a_new_parameter_changes_the_signature() -> None:
    before = export.parameters_from_input_schema({"properties": {"a": {"type": "string"}}})
    after = export.parameters_from_input_schema(
        {"properties": {"a": {"type": "string"}, "b": {"type": "boolean"}}}
    )

    assert export.signature(before) != export.signature(after)


def test_a_tool_without_a_declared_class_fails_the_export() -> None:
    registered = [{"name": "brand_new_tool", "inputSchema": {"properties": {}}}]

    with pytest.raises(ValueError, match="brand_new_tool"):
        export.build_surface(registered, contracts={})


# --- the committed artifact -----------------------------------------------


def test_committed_surface_validates(validator, surface) -> None:
    assert list(validator.iter_errors(surface)) == []


def test_committed_surface_matches_the_registry(surface) -> None:
    import server

    registered = sorted(t.name for t in asyncio.run(server.mcp.list_tools()))

    assert [t["name"] for t in surface["tools"]] == registered
    assert surface["tool_count"] == len(registered)


def test_classes_match_tool_contracts(surface) -> None:
    declared = {
        t["name"]: t["class"]
        for t in json.loads(CONTRACTS.read_text(encoding="utf-8"))["tools"]
    }

    assert {t["name"]: t["safety_class"] for t in surface["tools"]} == declared


def test_committed_surface_is_current() -> None:
    assert export.render(export.current_surface()) == SURFACE.read_text(encoding="utf-8")
