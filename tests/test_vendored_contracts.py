"""Contracts mq-mcp consumes but does not own.

`mq.runtime-identity.v1` is mq-agent's contract. mq-mcp has always produced it
— `mq-mcp/runtime_identity.py` builds a record and `/runtime-identity` serves
it — and produced it without importing anything, which is why a copy of the
schema has lived here as a test fixture.

Brain ingress makes mq-mcp a *consumer* as well: a record arriving from another
component has to be checked before it is written beside evidence. A schema that
runtime validates against is no longer a fixture, so the copy moved to
`schemas/vendor/` where its status is visible, and the no-import rule stays.

A vendored copy is only worth having while it is the same contract. The test
that matters here is therefore the drift test: when the canonical file is
reachable, the copy must equal it byte for byte. When it is not — CI, or any
machine without the sibling checkout — the copy is still checked against
everything that can be verified locally, and drift is reported as unverified
rather than assumed absent.

Why a copy at all, when `model_routing.py` reads mq-agent's schemas straight
from the sibling checkout: those tools cannot work without mq-agent anyway and
answer `mq-agent-unavailable` when it is missing. Ingress can be reached by a
record whether or not mq-agent's source tree is on this disk, and a validator
that disappears with a checkout would fail open exactly when it is needed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]

#: Where runtime reads it. Not under tests/ — production depends on this file.
VENDORED = ROOT / "schemas" / "vendor" / "mq.runtime-identity.v1.schema.json"

#: The owner's copy, when this machine has one. MQ_AGENT_HOME is how mq-mcp
#: already locates the sibling checkout — see mq-mcp/model_routing.py.
CANONICAL = (
    Path(os.environ.get("MQ_AGENT_HOME", Path.home() / "mq-agent")).expanduser()
    / "schemas"
    / "runtime_identity.schema.json"
)

CONTRACT_ID = "mq.runtime-identity.v1"


def test_vendored_schema_is_present():
    """Runtime validation needs the file, so its absence is a failure, not a skip."""
    assert VENDORED.is_file(), f"vendored contract missing: {VENDORED}"


def test_vendored_schema_is_a_usable_json_schema():
    schema = json.loads(VENDORED.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_vendored_schema_declares_the_contract_it_claims_to_be():
    """A copy under the wrong name would validate incoming records against the
    wrong contract while looking correct in every import."""
    schema = json.loads(VENDORED.read_text(encoding="utf-8"))
    assert schema["properties"]["schema"]["const"] == CONTRACT_ID


def test_vendored_copy_matches_the_canonical_schema():
    """Drift, checked where it can be: the owner's file is not always present."""
    if not CANONICAL.is_file():
        pytest.skip(f"canonical mq-agent schema not on this machine: {CANONICAL}")
    assert VENDORED.read_bytes() == CANONICAL.read_bytes(), (
        f"vendored copy has drifted from {CANONICAL}. "
        "mq-agent owns this contract: re-vendor rather than editing the copy."
    )
