"""The Class C surface, gated on the provenance the record arrives with.

`brain_record_review` writes into the operator's vault. Until now it accepted
whatever it was handed and wrote it, so a review produced by an unidentifiable
runtime and one produced by a verified one left identical notes.

The tool now reduces the ingress decision before writing and records the result
with the evidence. Two properties matter more than the rest:

- a refusal **writes nothing** — a decision that arrives after the file exists
  is not a gate;
- a record with no provenance still says so. Absence is written down, never
  filled in.

Callers that predate the contract send neither argument and keep working.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import server  # noqa: E402


LOCAL_COMMIT = "aaaaaaa"
RTP010 = "RTP010_RUNNING_CHECKOUT_MISMATCH"


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
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MQ_OBSIDIAN_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def pinned_identity(monkeypatch: pytest.MonkeyPatch) -> dict:
    """A fixed local identity, so the tests are about policy, not this checkout."""
    local = identity("mq-mcp", commit=LOCAL_COMMIT)
    monkeypatch.setattr(server._runtime_identity, "identity", lambda: dict(local))
    return local


@pytest.fixture
def producer() -> dict:
    return identity("mq-agent", commit="df6014f", version="1.28.0")


@pytest.fixture
def observation() -> dict:
    return {
        "component": "mq-mcp",
        "running": identity("mq-mcp", commit=LOCAL_COMMIT),
        "findings": [],
    }


def record(**kwargs):
    base = {
        "source": "repo-signal:mq-mcp",
        "finding_count": 2,
        "top_risks": ["no CI badge"],
        "suggested_next_steps": ["add one"],
    }
    return server.brain_record_review(**{**base, **kwargs})


def reviews(vault: Path) -> list[Path]:
    return sorted((vault / "reviews").glob("*.md"))


# ── the gate ─────────────────────────────────────────────────────────────────

def test_a_verified_producer_and_this_runtime_is_accepted(vault, pinned_identity, producer, observation):
    result = record(producer=producer, receiver_observation=observation)
    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept"
    assert len(reviews(vault)) == 1


def test_a_self_contradictory_producer_writes_nothing(vault, pinned_identity, producer, observation):
    """The property a gate has and a log line does not."""
    producer["commit"] = None  # still claiming verified
    result = record(producer=producer, receiver_observation=observation)
    assert result["ok"] is False
    assert result["ingress"]["decision"] == "refuse"
    assert "producer-identity-invalid" in result["ingress"]["reasons"]
    assert reviews(vault) == []


def test_an_observation_of_another_process_writes_nothing(vault, pinned_identity, producer, observation):
    observation["running"]["commit"] = "bbbbbbb"
    result = record(producer=producer, receiver_observation=observation)
    assert result["ok"] is False
    assert result["ingress"]["decision"] == "refuse"
    assert reviews(vault) == []


def test_a_refusal_says_why(vault, pinned_identity, producer, observation):
    producer["identity_quality"] = "partial"  # but carries a commit
    result = record(producer=producer, receiver_observation=observation)
    assert "producer-identity-invalid" in result["error"]


# ── backward compatibility ───────────────────────────────────────────────────

def test_a_caller_that_sends_no_provenance_still_writes(vault, pinned_identity):
    """mq-agent 1.28 in the field sends neither argument."""
    result = record()
    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept_with_warning"
    assert "producer-identity-missing" in result["ingress"]["reasons"]
    assert "receiver-observation-missing" in result["ingress"]["reasons"]
    assert len(reviews(vault)) == 1


def test_a_stale_receiver_is_written_with_its_finding(vault, pinned_identity, producer, observation):
    """The case the track exists for: this process runs A, the checkout has
    moved to B, and the note does not look like an ordinary one."""
    observation["findings"] = [{"component": "mq-mcp", "code": RTP010}]
    result = record(producer=producer, receiver_observation=observation)
    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept_with_warning"
    assert RTP010 in reviews(vault)[0].read_text(encoding="utf-8")


# ── what the note carries ────────────────────────────────────────────────────

def test_the_note_records_the_decision_and_the_producer(vault, pinned_identity, producer, observation):
    record(producer=producer, receiver_observation=observation)
    content = reviews(vault)[0].read_text(encoding="utf-8")
    assert "ingress_decision: accept" in content
    assert "mq-agent" in content
    assert "df6014f" in content


def test_absent_provenance_is_written_as_absent_not_invented(vault, pinned_identity):
    record()
    content = reviews(vault)[0].read_text(encoding="utf-8")
    assert "ingress_decision: accept_with_warning" in content
    assert "producer-identity-missing" in content
    assert "mq-agent" not in content


# ── the wiring is real ───────────────────────────────────────────────────────

def test_the_tool_uses_this_processs_own_captured_identity(vault, producer):
    """Not a pinned fixture: the observation is built from what this runtime
    actually reports, so a tool wired to something else fails here."""
    live = server._runtime_identity.identity()
    if live["identity_quality"] != "verified":
        pytest.skip(f"this runtime is {live['identity_quality']}; nothing to bind to")
    result = record(
        producer=producer,
        receiver_observation={
            "component": "mq-mcp",
            "running": {k: live[k] for k in (
                "schema", "component", "version", "commit", "install_type", "identity_quality"
            )},
            "findings": [],
        },
    )
    assert result["ok"] is True
    assert result["ingress"]["decision"] == "accept"


def test_an_observation_of_a_different_live_commit_is_refused(vault, producer):
    live = server._runtime_identity.identity()
    if live["identity_quality"] != "verified":
        pytest.skip(f"this runtime is {live['identity_quality']}; nothing to contradict")
    wrong = {k: live[k] for k in (
        "schema", "component", "version", "commit", "install_type", "identity_quality"
    )}
    wrong["commit"] = "0" * 7 if not live["commit"].startswith("0") else "1" * 7
    result = record(
        producer=producer,
        receiver_observation={"component": "mq-mcp", "running": wrong, "findings": []},
    )
    assert result["ok"] is False
    assert reviews(vault) == []


def test_an_unreadable_contract_refuses_rather_than_writing(vault, pinned_identity, producer, observation, monkeypatch, tmp_path):
    """No contract to check against is not the same as nothing to check."""
    monkeypatch.setattr(server._brain_ingress, "SCHEMA_PATH", tmp_path / "gone.json")
    monkeypatch.setattr(server._brain_ingress, "_VALIDATOR", None)
    result = record(producer=producer, receiver_observation=observation)
    assert result["ok"] is False
    assert result["ingress"]["reasons"] == ["ingress-contract-unavailable"]
    assert reviews(vault) == []
