"""The review engine must not report gaps that are not there.

Every case below is taken from a real `review_repo` run against
`mq-mcp/release_gate/`, where the model reported a missing module docstring in
a file whose first line is one, asked for return annotations on functions that
already carried them, and placed all fifteen findings on wrong lines with a
drift that grew from +7 to +285 through the file.

A finding nobody can trust costs more than no finding at all: it sends a reader
to the wrong line to look for a gap that does not exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from review_engine.finding_verifier import verify_findings
from review_engine.severity_engine import Severity, parse_findings

SOURCE = '''"""Deterministic Release Gate v2 checks."""
from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_tests_pass(repo: Path) -> str:
    return "ok"


def check_documented(repo: Path) -> str:
    """Already documented, and the return type is annotated."""
    return "ok"


def undocumented_and_untyped(repo):
    return "ok"
'''


def _finding(text: str):
    findings = parse_findings(text)
    assert len(findings) == 1, f"fixture did not parse: {text!r}"
    return findings[0]


def test_module_docstring_claim_is_dropped_when_one_exists():
    """The real run reported this against a file whose line 1 is a docstring."""
    finding = _finding(
        "[MISSING] checks.py:1\n"
        "Module has no module-level docstring; add a top-level summary."
    )
    kept, dropped = verify_findings("checks.py", SOURCE, [finding])
    assert kept == []
    assert len(dropped) == 1
    assert "module docstring" in dropped[0].lower()


def test_return_annotation_claim_is_dropped_when_already_annotated():
    finding = _finding(
        "[SUGGESTION] checks.py:34\n"
        "Add a return type annotation to check_tests_pass function signature "
        "to improve type clarity."
    )
    kept, dropped = verify_findings("checks.py", SOURCE, [finding])
    assert kept == []
    assert dropped and "check_tests_pass" in dropped[0]


def test_docstring_claim_is_dropped_when_the_function_has_one():
    finding = _finding(
        "[MISSING] checks.py:99\n"
        "Public function check_documented is missing a docstring; add a "
        "one-line description."
    )
    kept, dropped = verify_findings("checks.py", SOURCE, [finding])
    assert kept == []


def test_a_real_gap_survives():
    """Verification must not become a filter that swallows true findings."""
    finding = _finding(
        "[MISSING] checks.py:1\n"
        "Public function undocumented_and_untyped is missing a docstring."
    )
    kept, dropped = verify_findings("checks.py", SOURCE, [finding])
    assert len(kept) == 1
    assert dropped == []


def test_wrong_line_is_corrected_to_the_real_one():
    """The drift is the reason findings could not be trusted at all."""
    finding = _finding(
        "[MISSING] checks.py:412\n"
        "Public function undocumented_and_untyped is missing a docstring."
    )
    kept, _ = verify_findings("checks.py", SOURCE, [finding])
    assert len(kept) == 1
    expected = SOURCE.splitlines().index("def undocumented_and_untyped(repo):") + 1
    assert kept[0].line == expected, f"{kept[0].location} != line {expected}"


def test_documenting_the_return_type_in_prose_is_not_an_annotation_claim():
    """A finding about docstring *content* is not refuted by an annotation.

    These two read alike and mean different things; collapsing them would drop
    a legitimate finding as though it were a hallucination.
    """
    finding = _finding(
        "[MISSING] checks.py:1\n"
        "Public function check_documented has a docstring but does not "
        "explicitly document the return type; add return type info in the "
        "docstring."
    )
    kept, dropped = verify_findings("checks.py", SOURCE, [finding])
    assert len(kept) == 1, f"wrongly dropped: {dropped}"


def test_unknown_symbol_keeps_the_finding_untouched():
    """Unverifiable is not the same as false."""
    finding = _finding(
        "[WARNING] checks.py:7\nThis file mixes two concerns."
    )
    kept, dropped = verify_findings("checks.py", SOURCE, [finding])
    assert len(kept) == 1
    assert kept[0].location == "checks.py:7"


def test_non_python_and_unparseable_files_pass_through_unchanged():
    findings = [_finding("[NOTE] notes.md:3\nSomething about the prose.")]
    kept, dropped = verify_findings("notes.md", "# Title\n", findings)
    assert len(kept) == 1 and dropped == []

    broken = [_finding("[NOTE] broken.py:3\nSomething.")]
    kept, dropped = verify_findings("broken.py", "def (((:\n", broken)
    assert len(kept) == 1 and dropped == []


def test_severity_and_body_are_preserved():
    finding = _finding(
        "[MISSING] checks.py:900\n"
        "Public function undocumented_and_untyped is missing a docstring."
    )
    kept, _ = verify_findings("checks.py", SOURCE, [finding])
    assert kept[0].severity is Severity.MISSING
    assert "undocumented_and_untyped" in kept[0].body
