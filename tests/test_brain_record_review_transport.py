"""The MCP boundary, not the reducer behind it.

`producer` and `receiver_observation` are the first object-typed parameters on
any mq-mcp tool. Everything else on the surface takes strings, numbers and
lists, so the way FastMCP describes and validates an object argument is
untested ground — and a client that cannot see the parameters, or that is
allowed to pass a string where a record belongs, breaks the gate without any
of the reducer's tests noticing.

These tests go through `mcp.list_tools()` and `mcp.call_tool()` rather than
calling the function, because that is the path a real caller takes.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import server  # noqa: E402


REQUIRED = {
    "source": "repo-signal:mq-mcp",
    "finding_count": 1,
    "top_risks": ["one"],
    "suggested_next_steps": ["two"],
}


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def schema() -> dict:
    tools = asyncio.run(server.mcp.list_tools())
    tool = next(t for t in tools if t.name == "brain_record_review")
    return tool.inputSchema


def call(arguments: dict):
    return asyncio.run(server.mcp.call_tool("brain_record_review", arguments))


def _property(schema: dict, name: str) -> dict:
    return schema["properties"][name]


def test_both_provenance_parameters_are_discoverable(schema):
    for name in ("producer", "receiver_observation"):
        assert name in schema["properties"], name


def test_neither_parameter_is_required(schema):
    """A caller written before the contract must stay a valid caller."""
    required = schema.get("required", [])
    assert "producer" not in required
    assert "receiver_observation" not in required


@pytest.mark.parametrize("name", ["producer", "receiver_observation"])
def test_a_parameter_accepts_an_object_or_null(schema, name):
    """Serialized however FastMCP chooses — anyOf, or a type list — as long as
    both an object and null are describable to a client."""
    described = str(_property(schema, name))
    assert "object" in described, described
    assert "null" in described, described


def test_a_caller_that_omits_both_still_works(vault):
    result = call(dict(REQUIRED))
    assert len(list((vault / "reviews").glob("*.md"))) == 1
    assert "accept_with_warning" in str(result)


def test_a_caller_that_sends_both_works(vault):
    live = server._runtime_identity.identity()
    result = call({
        **REQUIRED,
        "producer": {
            "schema": "mq.runtime-identity.v1",
            "component": "mq-agent",
            "version": "1.28.0",
            "commit": "df6014f",
            "install_type": "editable",
            "identity_quality": "verified",
        },
        "receiver_observation": {
            "component": "mq-mcp",
            "running": {k: live[k] for k in (
                "schema", "component", "version", "commit", "install_type", "identity_quality"
            )},
            "findings": [],
        },
    })
    assert len(list((vault / "reviews").glob("*.md"))) == 1
    assert "refuse" not in str(result)


@pytest.mark.parametrize("value", ["not-an-object", 7, ["mq-agent"]])
def test_a_non_object_argument_is_rejected_at_the_boundary(vault, value):
    """The transport refuses it, or the tool does. What must not happen is a
    write: a string where a record belongs is never valid provenance."""
    try:
        result = call({**REQUIRED, "producer": value})
    except Exception:
        pass
    else:
        assert "refuse" in str(result) or "error" in str(result), result
    assert list((vault / "reviews").glob("*.md")) == []
