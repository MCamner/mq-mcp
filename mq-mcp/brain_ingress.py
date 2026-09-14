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
