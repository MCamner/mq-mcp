"""The ingress decision: accept, warn, or refuse a record's provenance.

mq-agent owns the comparison that produces `RTP010`. mq-mcp does not repeat it
— it decides whether to accept evidence arriving under a provenance claim, and
it makes that decision from what it was told plus the one fact it already
holds: the identity this process captured at start.

The reducer is pure on purpose. No MCP surface, no write, no git probe, no
network. It exists as its own step so the policy is frozen and mutation-proven
before the Class C tool signature moves.

The distinction the tests keep returning to: **a mismatch is a warning, a
self-contradiction is a refusal.** Something being behind is a fact about the
stack. Something being impossible is a fact about the record.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "brain_ingress.py"

RTP010 = "RTP010_RUNNING_CHECKOUT_MISMATCH"
LOCAL_COMMIT = "aaaaaaa"
OTHER_COMMIT = "bbbbbbb"


def _load():
    spec = importlib.util.spec_from_file_location("mq_mcp_brain_ingress_reducer_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ingress():
    return _load()


def identity(component: str, *, commit: str | None, version: str | None = "2.1.0") -> dict:
    if version is None:
        quality, commit = "unknown", None
    elif commit is None:
        quality = "partial"
    else:
        quality = "verified"
    return {
        "schema": "mq.runtime-identity.v1",
        "component": component,
        "version": version,
        "commit": commit,
        "install_type": "editable",
        "identity_quality": quality,
    }


@pytest.fixture
def local() -> dict:
    """What this mq-mcp process captured at start."""
    return identity("mq-mcp", commit=LOCAL_COMMIT)


@pytest.fixture
def producer() -> dict:
    return identity("mq-agent", commit="df6014f", version="1.28.0")


@pytest.fixture
def observation() -> dict:
    """mq-agent's observation of the receiver, agreeing with the receiver."""
    return {
        "component": "mq-mcp",
        "running": identity("mq-mcp", commit=LOCAL_COMMIT),
        "checkout_head": LOCAL_COMMIT,
        "running_matches_checkout": True,
        "findings": [],
    }


def reduce(ingress, *, producer=None, observation=None, local):
    return ingress.reduce_brain_ingress(
        producer=producer,
        receiver_observation=observation,
        receiver_identity=local,
    )


# ── accept ───────────────────────────────────────────────────────────────────

def test_verified_producer_and_matching_receiver_is_accepted(ingress, producer, observation, local):
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "accept"
    assert result["reasons"] == []
    assert result["findings"] == []


# ── refuse: the record contradicts itself ────────────────────────────────────

def test_producer_claiming_verified_without_a_commit_is_refused(ingress, producer, observation, local):
    producer["commit"] = None
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "producer-identity-invalid" in result["reasons"]


def test_producer_claiming_partial_with_a_commit_is_refused(ingress, producer, observation, local):
    producer["identity_quality"] = "partial"
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "producer-identity-invalid" in result["reasons"]


def test_a_receiver_running_identity_that_fails_the_contract_is_refused(ingress, producer, observation, local):
    observation["running"]["identity_quality"] = "unknown"  # still carries a version
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "receiver-identity-invalid" in result["reasons"]


def test_a_running_identity_for_another_component_is_refused(ingress, producer, observation, local):
    observation["running"] = identity("mq-other", commit=LOCAL_COMMIT)
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "receiver-subject-mismatch" in result["reasons"]


def test_an_observation_about_another_component_is_refused(ingress, producer, observation, local):
    observation["component"] = "mq-other"
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "receiver-subject-mismatch" in result["reasons"]


def test_a_finding_about_another_component_is_refused(ingress, producer, observation, local):
    """An RTP010 naming mq-agent inside an observation about mq-mcp is not a
    receiver finding. Requiring the subjects to agree makes it a structural
    error rather than something ingress has to interpret."""
    observation["findings"] = [{"component": "mq-agent", "code": RTP010}]
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "receiver-finding-subject-mismatch" in result["reasons"]


def test_an_observation_of_a_different_process_is_refused(ingress, producer, observation, local):
    """The claim is about some mq-mcp, but not this one. Accepting it would
    file the decision under a runtime that never saw the record."""
    observation["running"]["commit"] = OTHER_COMMIT
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "refuse"
    assert "receiver-running-commit-mismatch" in result["reasons"]


@pytest.mark.parametrize("value", [None, "mq-agent", 7, []])
def test_an_observation_that_is_not_a_record_is_refused(ingress, producer, local, value):
    result = reduce(ingress, producer=producer, observation=value, local=local)
    if value is None:
        assert result["decision"] == "accept_with_warning"
    else:
        assert result["decision"] == "refuse"


# ── warn: something is behind, or was never observed ─────────────────────────

def test_a_missing_producer_warns_and_still_writes(ingress, observation, local):
    """Older callers send nothing. They must keep working."""
    result = reduce(ingress, producer=None, observation=observation, local=local)
    assert result["decision"] == "accept_with_warning"
    assert "producer-identity-missing" in result["reasons"]


def test_a_missing_receiver_observation_warns(ingress, producer, local):
    result = reduce(ingress, producer=producer, observation=None, local=local)
    assert result["decision"] == "accept_with_warning"
    assert "receiver-observation-missing" in result["reasons"]


def test_a_stale_receiver_warns_and_keeps_the_finding(ingress, producer, observation, local):
    """The case the whole track exists for: this process runs A, the checkout
    has moved to B, and the record says so instead of looking normal."""
    observation["checkout_head"] = OTHER_COMMIT
    observation["running_matches_checkout"] = False
    observation["findings"] = [{"component": "mq-mcp", "code": RTP010}]
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "accept_with_warning"
    assert result["findings"] == [{"component": "mq-mcp", "code": RTP010}]


def test_a_receiver_identity_without_a_commit_cannot_be_tied_and_warns(ingress, producer, observation, local):
    """Absence is not contradiction. A partial identity cannot be shown to be
    this process, and cannot be shown not to be either."""
    observation["running"] = identity("mq-mcp", commit=None)
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "accept_with_warning"
    assert "receiver-running-commit-unverifiable" in result["reasons"]


def test_a_local_identity_without_a_commit_cannot_verify_and_warns(ingress, producer, observation):
    """Same rule from the other side: this process may not know its own commit."""
    local = identity("mq-mcp", commit=None)
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["decision"] == "accept_with_warning"
    assert "receiver-running-commit-unverifiable" in result["reasons"]


# ── precedence and evidence retention ────────────────────────────────────────

def test_refusal_outranks_a_warning(ingress, observation, local):
    producer = identity("mq-agent", commit="df6014f", version="1.28.0")
    producer["identity_quality"] = "partial"
    result = reduce(ingress, producer=producer, observation=None, local=local)
    assert result["decision"] == "refuse"
    assert "producer-identity-invalid" in result["reasons"]


def test_every_reason_survives_a_decision_that_was_already_settled(ingress, observation, local):
    """Two warnings still produce one decision, and neither reason is dropped:
    the record is the evidence, not just the verdict."""
    observation["running_matches_checkout"] = False
    observation["checkout_head"] = OTHER_COMMIT
    observation["findings"] = [{"component": "mq-mcp", "code": RTP010}]
    result = reduce(ingress, producer=None, observation=observation, local=local)
    assert result["decision"] == "accept_with_warning"
    assert "producer-identity-missing" in result["reasons"]
    assert "receiver-findings-present" in result["reasons"]
    assert result["findings"] == [{"component": "mq-mcp", "code": RTP010}]


def test_the_same_payload_always_gives_the_same_decision(ingress, producer, observation, local):
    first = reduce(ingress, producer=producer, observation=observation, local=local)
    second = reduce(ingress, producer=dict(producer), observation=dict(observation), local=dict(local))
    assert first == second


def test_reasons_are_ordered_deterministically(ingress, observation, local):
    observation["findings"] = [{"component": "mq-mcp", "code": RTP010}]
    result = reduce(ingress, producer=None, observation=observation, local=local)
    assert result["reasons"] == sorted(result["reasons"])


def test_the_reducer_does_not_recompute_the_comparison(ingress, producer, observation, local):
    """mq-agent owns running_matches_checkout. A mismatch mq-agent reported no
    finding for is mq-agent's bug; reconstructing RTP010 here would be a second
    implementation of the comparison, free to disagree with the first."""
    observation["running_matches_checkout"] = False
    observation["checkout_head"] = OTHER_COMMIT
    observation["findings"] = []
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert result["findings"] == []
    assert not any("RTP" in reason for reason in result["reasons"])


def test_the_reducer_carries_no_remedy(ingress, producer, observation, local):
    """RTP semantics stay mq-agent's. Ingress decides receipt, not repair."""
    observation["findings"] = [{"component": "mq-mcp", "code": RTP010}]
    observation["running_matches_checkout"] = False
    result = reduce(ingress, producer=producer, observation=observation, local=local)
    assert set(result) == {"decision", "findings", "reasons"}
    assert "next_action" not in str(result)


def test_the_reducer_touches_nothing(ingress):
    """Pure by construction, not by intention: no subprocess, no network, no
    filesystem beyond the vendored contract the validator already reads."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "urllib", "requests", "socket", "httpx", "open("):
        assert forbidden not in source, forbidden
