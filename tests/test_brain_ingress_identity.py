"""Validating a runtime identity that arrived from somewhere else.

mq-mcp has always produced `mq.runtime-identity.v1`. Brain ingress has to read
one: a record travelling with evidence says which runtime produced it, and a
record that contradicts its own contract must not be written beside evidence as
though it were a fact.

Two properties are worth testing beyond "the schema is applied". The validator
must **fail closed** — an unreadable contract cannot mean "nothing was wrong" —
and its messages must name the field, never quote the value, because a record
carries executable, module_path and source_path and those are the operator's
private paths.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "brain_ingress.py"
IDENTITY_MODULE_PATH = ROOT / "mq-mcp" / "runtime_identity.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ingress():
    return _load(MODULE_PATH, "mq_mcp_brain_ingress_test")


@pytest.fixture
def verified() -> dict:
    return {
        "schema": "mq.runtime-identity.v1",
        "component": "mq-agent",
        "version": "1.28.0",
        "commit": "df6014f",
        "install_type": "editable",
        "identity_quality": "verified",
    }


def test_this_runtimes_own_identity_validates(ingress):
    """The producer and the validator agree. If they ever stop agreeing, one of
    the two is wrong and the suite should say so here rather than in ingress."""
    identity = _load(IDENTITY_MODULE_PATH, "mq_mcp_runtime_identity_ingress_test")
    assert ingress.identity_errors(identity.identity()) == []


def test_a_well_formed_record_has_no_errors(ingress, verified):
    assert ingress.identity_errors(verified) == []


def test_optional_fields_are_allowed(ingress, verified):
    assert ingress.identity_errors({
        **verified,
        "started_at": "2026-09-14T09:00:00Z",
        "executable": "/usr/bin/python3",
        "module_path": "/somewhere/mq_agent",
        "source_path": None,
    }) == []


@pytest.mark.parametrize(
    "mutation, field",
    [
        ({"commit": None}, "commit"),                       # verified needs one
        ({"version": None}, "version"),                     # and a version
        ({"identity_quality": "partial"}, "commit"),        # partial carries none
        ({"identity_quality": "unknown"}, "version"),       # unknown carries neither
        ({"identity_quality": "excellent"}, "identity_quality"),
        ({"schema": "mq.runtime-identity.v2"}, "schema"),
        ({"commit": "ZZZZ"}, "commit"),
        ({"install_type": "homebrew"}, "install_type"),
        ({"component": ""}, "component"),
    ],
)
def test_a_record_that_contradicts_the_contract_is_rejected(ingress, verified, mutation, field):
    errors = ingress.identity_errors({**verified, **mutation})
    assert errors, f"{mutation} should not validate"
    assert any(field in message for message in errors), errors


def test_a_missing_required_field_is_rejected(ingress, verified):
    del verified["install_type"]
    assert ingress.identity_errors(verified)


def test_an_unknown_field_is_rejected(ingress, verified):
    """A record carrying more than the contract describes is not a richer
    record; it is one this validator cannot speak for."""
    assert ingress.identity_errors({**verified, "blocks_release": True})


@pytest.mark.parametrize("value", [None, "mq-agent", 7, [], ["mq-agent"]])
def test_something_that_is_not_a_record_is_rejected(ingress, value):
    assert ingress.identity_errors(value)


def test_messages_name_the_field_and_never_quote_the_value(ingress, verified):
    """The record carries private paths. A validator that echoed the instance
    would write them into whatever logs or refusal messages it reaches."""
    secret = "/Users/someone/private/checkout/bin/python"
    errors = ingress.identity_errors({
        **verified,
        "executable": {"unexpected": secret},
        "source_path": {"unexpected": secret},
    })
    assert errors
    assert any("executable" in message for message in errors), errors
    assert not any(secret in message for message in errors), errors


def test_an_unreadable_contract_fails_closed(ingress, verified, monkeypatch, tmp_path):
    """Absence of the schema cannot read as absence of errors."""
    monkeypatch.setattr(ingress, "SCHEMA_PATH", tmp_path / "gone.json")
    monkeypatch.setattr(ingress, "_VALIDATOR", None)
    with pytest.raises(ingress.IdentityContractUnavailable):
        ingress.identity_errors(verified)


def test_the_validator_uses_the_vendored_contract(ingress):
    """Not a copy of the rules restated in Python, which would be free to
    disagree with the file the drift test protects."""
    assert ingress.SCHEMA_PATH == ROOT / "schemas" / "vendor" / "mq.runtime-identity.v1.schema.json"
    assert json.loads(ingress.SCHEMA_PATH.read_text())["properties"]["schema"]["const"] == (
        "mq.runtime-identity.v1"
    )


def test_no_mq_agent_code_is_imported(ingress):
    """The contract crosses the boundary. The implementation does not — the
    same rule runtime_identity.py keeps as a producer."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "import mq_agent" not in source
    assert "from mq_agent" not in source
