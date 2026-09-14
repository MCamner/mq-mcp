"""Checking a runtime identity that arrived with somebody else's evidence.

mq-mcp produces `mq.runtime-identity.v1` about itself in `runtime_identity.py`.
This module reads one: evidence written through mq-mcp can carry the identity of
the runtime that produced it, and a record that contradicts its own contract
must not be written beside evidence as though it were a fact.

mq-agent owns the contract. The schema is vendored under `schemas/vendor/` and
validated from the file, never restated as Python — a second copy of the rules
would be free to disagree with the one the drift test protects. No mq-agent
code is imported, which is the boundary the producer side has always kept.

Two decisions worth stating, because both differ from what the rest of the repo
does:

**Fail closed.** `learn_engine` falls back to an inline schema when its file
cannot be read, which is right for an extractor whose worst case is a rejected
candidate. Here the worst case is evidence admitted without a check, so an
unreadable contract raises rather than validating nothing.

**Messages name fields, never values.** A record carries `executable`,
`module_path` and `source_path` — the operator's private paths. jsonschema's
own messages quote the instance, so the description is built from the field
location and the schema's own expectation instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

#: The vendored contract. Owned by mq-agent; see schemas/vendor/README.md.
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "vendor"
    / "mq.runtime-identity.v1.schema.json"
)

CONTRACT_ID = "mq.runtime-identity.v1"

#: Built once, on first use. Module import must not depend on the file.
_VALIDATOR: Draft202012Validator | None = None


class IdentityContractUnavailable(RuntimeError):
    """The vendored contract could not be read, so nothing can be validated."""


def _validator() -> Draft202012Validator:
    global _VALIDATOR
    if _VALIDATOR is None:
        try:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        except Exception as exc:  # unreadable, missing, or not JSON
            raise IdentityContractUnavailable(
                f"cannot read {CONTRACT_ID} contract at {SCHEMA_PATH.name}"
            ) from exc
        _VALIDATOR = Draft202012Validator(schema)
    return _VALIDATOR


def _location(error: Any) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "<record>"


def _describe(error: Any) -> str:
    """One failure, named without quoting what the record carried.

    Everything used here comes from the schema or from field names. The
    instance itself is never interpolated.
    """
    location = _location(error)

    if error.validator == "additionalProperties" and isinstance(error.instance, dict):
        declared = set(error.schema.get("properties", {}))
        unknown = sorted(set(error.instance) - declared)
        return f"{location}: unknown field(s): {', '.join(unknown)}"

    if error.validator == "required" and isinstance(error.instance, dict):
        missing = sorted(k for k in error.validator_value if k not in error.instance)
        return f"{location}: missing required field(s): {', '.join(missing)}"

    if error.validator in {"const", "enum", "type", "pattern", "minLength"}:
        return f"{location}: fails {error.validator}={json.dumps(error.validator_value)}"

    return f"{location}: fails {error.validator}"


def identity_errors(record: Any) -> list[str]:
    """Every way `record` fails `mq.runtime-identity.v1`. Empty means valid.

    Raises IdentityContractUnavailable if the contract cannot be read: no
    answer is not the same as no problem.
    """
    errors = {_describe(error) for error in _validator().iter_errors(record)}
    return sorted(errors)


def is_valid_identity(record: Any) -> bool:
    """Convenience over identity_errors. Raises the same way when unreadable."""
    return not identity_errors(record)


# ── the ingress decision ─────────────────────────────────────────────────────
#
# Pure. Given what arrived and the identity this process captured at start, it
# returns a decision and the evidence behind it. It reads no file beyond the
# vendored contract, runs no command, and reaches no network.
#
# The comparison that produces RTP010 belongs to mq-agent, which owns the
# reason codes and already computes `running_matches_checkout`. mq-mcp holds
# exactly one fact mq-agent cannot forge: which commit this process is. So the
# reducer checks that the observation is about *this* runtime and otherwise
# consumes what it was told.

ACCEPT = "accept"
ACCEPT_WITH_WARNING = "accept_with_warning"
REFUSE = "refuse"

#: The only component an observation delivered here can be about.
RECEIVER_COMPONENT = "mq-mcp"


def _finding_reasons(observation: dict, subject: str) -> tuple[list[dict], list[str]]:
    """Validated findings, and why any were rejected.

    A finding must name the same component the observation is about. An RTP010
    naming mq-agent inside an observation about mq-mcp is not a receiver
    finding, and requiring the subjects to agree makes that a structural error
    rather than something ingress has to interpret.
    """
    raw = observation.get("findings", [])
    if not isinstance(raw, list):
        return [], ["receiver-observation-invalid"]

    findings: list[dict] = []
    reasons: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            reasons.append("receiver-observation-invalid")
            continue
        component, code = item.get("component"), item.get("code")
        if not isinstance(component, str) or not isinstance(code, str) or not code:
            reasons.append("receiver-observation-invalid")
            continue
        if component != subject:
            reasons.append("receiver-finding-subject-mismatch")
            continue
        findings.append({"component": component, "code": code})
    return findings, reasons


def _receiver_reasons(
    observation: Any,
    receiver_identity: dict,
) -> tuple[list[dict], list[str], list[str]]:
    """(findings, refusals, warnings) for the receiver half of the payload."""
    if observation is None:
        return [], [], ["receiver-observation-missing"]
    if not isinstance(observation, dict):
        return [], ["receiver-observation-invalid"], []

    refusals: list[str] = []
    warnings: list[str] = []

    subject = observation.get("component")
    if subject != RECEIVER_COMPONENT:
        refusals.append("receiver-subject-mismatch")

    running = observation.get("running")
    if not isinstance(running, dict) or identity_errors(running):
        refusals.append("receiver-identity-invalid")
    elif running.get("component") != RECEIVER_COMPONENT:
        refusals.append("receiver-subject-mismatch")
    else:
        claimed = running.get("commit")
        local = receiver_identity.get("commit")
        if not claimed or not local:
            # Absence is not contradiction. An identity carrying no commit
            # cannot be shown to be this process, or shown not to be.
            warnings.append("receiver-running-commit-unverifiable")
        elif claimed != local:
            # A real mq-mcp, but not the one holding this record.
            refusals.append("receiver-running-commit-mismatch")

    findings, finding_reasons = _finding_reasons(
        observation, subject if isinstance(subject, str) else RECEIVER_COMPONENT
    )
    refusals.extend(finding_reasons)
    return findings, refusals, warnings


def reduce_brain_ingress(
    *,
    producer: dict | None,
    receiver_observation: dict | None,
    receiver_identity: dict,
) -> dict[str, Any]:
    """Decide whether evidence may be written under the provenance it carries.

    Precedence, frozen: a record that contradicts itself is refused; something
    merely absent or behind is a warning; everything else is accepted.

    1. the producer identity fails its contract         refuse
    2. the receiver identity fails its contract         refuse
    3. the observation is about another component       refuse
    4. the observation is about another mq-mcp process  refuse
    5. no producer identity                             warn
    6. no receiver observation                          warn
    7. the receiver carries findings                    warn
    8. otherwise                                        accept

    Every reason is kept even once the decision is settled — the record is the
    evidence, not just the verdict. No remedy is produced: RTP semantics stay
    with mq-agent, and ingress decides receipt, not repair.

    Raises IdentityContractUnavailable if the contract cannot be read.
    """
    if not isinstance(receiver_identity, dict):
        raise ValueError("receiver_identity must be this runtime's own identity record")

    refusals: list[str] = []
    warnings: list[str] = []

    if producer is None:
        # Callers that predate the contract send nothing. They keep working.
        warnings.append("producer-identity-missing")
    elif not isinstance(producer, dict) or identity_errors(producer):
        refusals.append("producer-identity-invalid")

    findings, receiver_refusals, receiver_warnings = _receiver_reasons(
        receiver_observation, receiver_identity
    )
    refusals.extend(receiver_refusals)
    warnings.extend(receiver_warnings)

    if findings:
        warnings.append("receiver-findings-present")

    if refusals:
        decision = REFUSE
    elif warnings:
        decision = ACCEPT_WITH_WARNING
    else:
        decision = ACCEPT

    return {
        "decision": decision,
        "findings": findings,
        "reasons": sorted(set(refusals) | set(warnings)),
    }
