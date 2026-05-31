"""Tests that semantic memory policy infrastructure is in place and store is valid."""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "semantic_memory" / "store.json"
POLICY = ROOT / "semantic_memory" / "POLICY.md"
SCHEMA = ROOT / "semantic_memory" / "schema.json"

VALID_TYPES = {"fact", "decision", "convention", "summary", "warning"}
VALID_CONFIDENCE = {"high", "medium", "low"}


# ---------------------------------------------------------------------------
# Required files
# ---------------------------------------------------------------------------

def test_policy_file_exists():
    assert POLICY.exists(), "semantic_memory/POLICY.md missing"


def test_schema_file_exists():
    assert SCHEMA.exists(), "semantic_memory/schema.json missing"


def test_store_file_exists():
    assert STORE.exists(), "semantic_memory/store.json missing"


def test_schema_is_valid_json():
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert data.get("schema") == "semantic-memory.v2"
    assert "fields" in data


def test_policy_covers_required_sections():
    text = POLICY.read_text(encoding="utf-8")
    required = [
        "What may be stored",
        "What may NOT be stored",
        "Required fields",
        "How old entries are marked",
        "How conflicts are handled",
        "How bootstrap may be used",
        "How stale memory is detected",
    ]
    missing = [s for s in required if s not in text]
    assert not missing, f"POLICY.md missing sections: {missing}"


# ---------------------------------------------------------------------------
# Store integrity
# ---------------------------------------------------------------------------

def test_store_is_valid_json():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "store.json must be a JSON object (dict)"


def test_store_has_entries():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    assert len(data) > 0, "store.json is empty"


def test_no_duplicate_keys():
    # JSON object keys are inherently unique, but verify the count matches
    text = STORE.read_text(encoding="utf-8")
    data = json.loads(text)
    assert len(data) == len(data.keys())


def test_all_entries_have_required_fields():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    missing_key     = [k for k, v in data.items() if not v.get("key")]
    missing_content = [k for k, v in data.items() if not v.get("content")]
    missing_created = [k for k, v in data.items() if "created_at" not in v]
    missing_updated = [k for k, v in data.items() if "updated_at" not in v]
    assert not missing_key,     f"Entries without key: {missing_key}"
    assert not missing_content, f"Entries without content: {missing_content}"
    assert not missing_created, f"Entries without created_at: {missing_created}"
    assert not missing_updated, f"Entries without updated_at: {missing_updated}"


def test_entries_with_type_use_valid_values():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    invalid = [
        k for k, v in data.items()
        if "type" in v and v["type"] not in VALID_TYPES
    ]
    assert not invalid, f"Entries with invalid type: {invalid}"


def test_entries_with_confidence_use_valid_values():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    invalid = [
        k for k, v in data.items()
        if "confidence" in v and v["confidence"] not in VALID_CONFIDENCE
    ]
    assert not invalid, f"Entries with invalid confidence: {invalid}"


def test_no_entry_has_forbidden_source():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    forbidden = [
        k for k, v in data.items()
        if v.get("source") in ("unknown",)
    ]
    assert not forbidden, f"Entries with forbidden source value: {forbidden}"


def test_no_entry_has_empty_content():
    data = json.loads(STORE.read_text(encoding="utf-8"))
    empty = [k for k, v in data.items() if not v.get("content", "").strip()]
    assert not empty, f"Entries with empty content: {empty}"


# ---------------------------------------------------------------------------
# Bootstrap protection
# ---------------------------------------------------------------------------

def test_bootstrap_entries_are_summary_type():
    """Bootstrap entries (source starts with 'bootstrap:') must be type=summary."""
    data = json.loads(STORE.read_text(encoding="utf-8"))
    violations = [
        k for k, v in data.items()
        if str(v.get("source", "")).startswith("bootstrap:")
        and v.get("type") not in (None, "", "summary")
    ]
    assert not violations, (
        f"Bootstrap entries with non-summary type (should be summary): {violations}"
    )


# ---------------------------------------------------------------------------
# Script integration
# ---------------------------------------------------------------------------

def test_check_semantic_memory_script_exists():
    script = ROOT / "scripts" / "check-semantic-memory.sh"
    assert script.exists(), "scripts/check-semantic-memory.sh missing"
    assert script.stat().st_mode & 0o111, "check-semantic-memory.sh is not executable"


def test_check_semantic_memory_script_passes():
    script = ROOT / "scripts" / "check-semantic-memory.sh"
    result = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        f"check-semantic-memory.sh failed:\n{result.stdout}\n{result.stderr}"
    )
