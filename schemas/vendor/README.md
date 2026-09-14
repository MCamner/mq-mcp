# Vendored external contracts

Contracts owned by another MQ repository, copied here because mq-mcp runtime
validates against them. Not fixtures: production code reads these files.

| | |
| --- | --- |
| Owner | the repository named per contract below |
| Consumer | mq-mcp runtime |
| Copy | vendored, byte-identical to the owner's file |
| Imports | none — no code from the owning repo is imported |
| Drift | `tests/test_vendored_contracts.py` |

The rule that makes vendoring safe: **a copy is never edited here.** A contract
changes in the repository that owns it, and the new version is re-vendored.
Editing the copy would let mq-mcp accept records the owner's own validator
rejects, silently and only on this side of the boundary.

## `mq.runtime-identity.v1.schema.json`

* **Owner:** `mq-agent` — `schemas/runtime_identity.schema.json`
* **Consumed by:** brain ingress, to validate producer and receiver identity
  records arriving with evidence.
* **Also produced by mq-mcp:** `mq-mcp/runtime_identity.py` reports this
  component's own identity. Producing it shares no code with validating it,
  which is the same boundary the producer has always kept.

`mq-mcp/model_routing.py` reads other mq-agent schemas live from the sibling
checkout instead of vendoring them. That is right there and wrong here: those
tools cannot run without mq-agent and report `mq-agent-unavailable` when it is
gone, while ingress must still validate a record that arrives on a machine with
no mq-agent checkout at all.

The drift test compares against the owner's file when this machine has the
sibling checkout (`MQ_AGENT_HOME`, else `~/mq-agent`) and skips when it does
not, so drift is reported as unverified rather than assumed absent.
