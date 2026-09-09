"""Check review findings against the file before they are shown.

The review model writes findings as free text, and two kinds of error in that
text are cheap to catch and expensive to leave in.

It reports gaps that are not there — a missing module docstring in a file whose
first line is one, a missing return annotation on a signature that carries it.
And it places findings on lines it arrived at by counting rather than reading:
in the run that prompted this module, all fifteen findings in one file were on
the wrong line, drifting from +7 near the top to +285 at the bottom.

Both are answerable from the syntax tree, so neither needs to reach a reader.
A finding that survives here is one whose claim the file does not contradict —
not one that is necessarily worth acting on. Nothing is invented and nothing is
rewritten but the line number, which is corrected only when the finding names a
symbol the file actually defines.

Only Python is checked. Everything else passes through untouched, because an
unverifiable finding is not the same as a false one.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from typing import Any

# "is missing a docstring", "lacks a docstring", "has no docstring".
# Deliberately not matched: "has a docstring but does not document X", which is
# a claim about what the docstring says, not about whether it exists.
_CLAIM_NO_DOCSTRING = re.compile(
    r"\b(?:missing|lacks|lacking|has no|without|no)\b[^.;]{0,40}\bdocstrings?\b",
    re.IGNORECASE,
)

_CLAIM_NO_MODULE_DOCSTRING = re.compile(
    r"\bmodule\b[^.;]{0,40}\bdocstrings?\b|\bdocstrings?\b[^.;]{0,20}\bat module level\b",
    re.IGNORECASE,
)

# An annotation claim is about the signature. "document the return type in the
# docstring" asks for prose and is left alone — the annotation being present
# does not answer it.
_CLAIM_NO_RETURN_ANNOTATION = re.compile(
    r"\breturn type\b[^.;]{0,60}\b(?:annotation|hint|signature)\b"
    r"|\b(?:annotation|hint)\b[^.;]{0,60}\breturn type\b"
    r"|\breturn\b[^.;]{0,20}\bannotation\b",
    re.IGNORECASE,
)

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class _Symbol:
    lineno: int
    has_docstring: bool
    has_return_annotation: bool


def _index(tree: ast.Module) -> dict[str, _Symbol]:
    """Every function and class in the file, by name.

    A name defined more than once (an overload, a method sharing a name with a
    function) is dropped rather than guessed at: a finding naming it cannot be
    tied to one definition, so its line is left as the model wrote it.
    """
    found: dict[str, list[_Symbol]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbol = _Symbol(
                lineno=node.lineno,
                has_docstring=ast.get_docstring(node) is not None,
                has_return_annotation=node.returns is not None,
            )
        elif isinstance(node, ast.ClassDef):
            symbol = _Symbol(
                lineno=node.lineno,
                has_docstring=ast.get_docstring(node) is not None,
                has_return_annotation=True,  # not applicable; never a gap
            )
        else:
            continue
        found.setdefault(node.name, []).append(symbol)
    return {name: entries[0] for name, entries in found.items() if len(entries) == 1}


def _subject(body: str, symbols: dict[str, _Symbol]) -> str | None:
    """The symbol a finding is about, if it names exactly one.

    Findings name their subject in prose ("Public function check_tests_pass is
    missing…"), so the body is scanned for identifiers the file defines. Two
    different names means the sentence is about a relationship, and correcting
    it to either one would move the finding somewhere it does not belong.
    """
    named = {word for word in _IDENTIFIER.findall(body) if word in symbols}
    return next(iter(named)) if len(named) == 1 else None


def verify_findings(
    file_path: str, content: str, findings: list[Any]
) -> tuple[list[Any], list[str]]:
    """Drop findings the file refutes, and correct the lines of those it does not.

    Returns the findings worth showing, and one plain-language reason per
    finding dropped — the reasons are for the operator, so a silent filter never
    stands between the model and the reader.
    """
    if not findings or not file_path.endswith(".py"):
        return list(findings), []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return list(findings), []

    module_has_docstring = ast.get_docstring(tree) is not None
    symbols = _index(tree)

    kept: list[Any] = []
    dropped: list[str] = []

    for finding in findings:
        body = getattr(finding, "body", "") or ""
        subject = _subject(body, symbols)

        # A claim about the module's own docstring names no function.
        if (
            subject is None
            and module_has_docstring
            and _CLAIM_NO_DOCSTRING.search(body)
            and _CLAIM_NO_MODULE_DOCSTRING.search(body)
        ):
            dropped.append(
                f"{file_path}: reported a missing module docstring; the file has one"
            )
            continue

        if subject is not None:
            symbol = symbols[subject]
            if symbol.has_docstring and _CLAIM_NO_DOCSTRING.search(body):
                dropped.append(
                    f"{file_path}: reported {subject}() as undocumented; it has a docstring"
                )
                continue
            if symbol.has_return_annotation and _CLAIM_NO_RETURN_ANNOTATION.search(body):
                dropped.append(
                    f"{file_path}: asked for a return annotation on {subject}(); "
                    f"the signature already carries one"
                )
                continue

            # Survived: anchor it to the definition rather than to the model's count.
            finding = _relocate(finding, file_path, symbol.lineno)

        kept.append(finding)

    return kept, dropped


def _relocate(finding: Any, file_path: str, lineno: int) -> Any:
    """Point a finding at the line its subject is actually defined on."""
    location = f"{file_path}:{lineno}"
    if getattr(finding, "location", None) == location:
        return finding
    try:
        return replace(finding, location=location)
    except Exception:
        try:
            finding.location = location
        except Exception:
            pass
        return finding
