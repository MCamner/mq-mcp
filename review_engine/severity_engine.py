"""
Severity Engine — mq-mcp review engine, Phase 2.3

Parses, validates, and formats review findings from the review model output.
Ensures output conforms to the comment-review contract severity schema.

Usage:
  from review_engine.severity_engine import parse_findings, format_summary
  findings = parse_findings(raw_review_text)
  print(format_summary(findings))
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    NOTE = "NOTE"
    SUGGESTION = "SUGGESTION"
    WARNING = "WARNING"
    MISSING = "MISSING"
    # Architecture-review severities (Phase 2 extension)
    ARCHITECTURE = "ARCHITECTURE"
    RISK = "RISK"
    # Risk-analysis severity (v1.5.0) — immediate exploitable vulnerability
    CRITICAL = "CRITICAL"


SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.RISK,
    Severity.ARCHITECTURE,
    Severity.WARNING,
    Severity.MISSING,
    Severity.SUGGESTION,
    Severity.NOTE,
]

_FINDING_PATTERN = re.compile(
    r"^\[(?P<severity>[A-Z]+)\]\s+(?P<location>\S+)\n(?P<body>.+?)(?=\n\[|\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass
class Finding:
    severity: Severity
    location: str
    body: str
    raw: str = field(repr=False, default="")

    @property
    def file(self) -> str:
        return self.location.split(":")[0] if ":" in self.location else self.location

    @property
    def line(self) -> int | None:
        parts = self.location.split(":")
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                pass
        return None

    def format(self) -> str:
        return f"[{self.severity.value}] {self.location}\n{self.body.strip()}"


def parse_findings(text: str) -> list[Finding]:
    """
    Parse structured review findings from raw model output.

    Extracts all [SEVERITY] location\\nbody blocks. Unknown severity labels
    are dropped and not included in the result.

    Returns findings sorted by severity (most severe first), then by line number.
    """
    findings: list[Finding] = []
    valid_labels = {s.value for s in Severity}

    for match in _FINDING_PATTERN.finditer(text):
        label = match.group("severity").upper()
        if label not in valid_labels:
            continue
        finding = Finding(
            severity=Severity(label),
            location=match.group("location").strip(),
            body=match.group("body").strip(),
            raw=match.group(0),
        )
        findings.append(finding)

    return sorted(
        findings,
        key=lambda f: (
            SEVERITY_ORDER.index(f.severity) if f.severity in SEVERITY_ORDER else 99,
            f.line or 0,
        ),
    )


def format_summary(findings: list[Finding], file_path: str = "") -> str:
    """
    Return a human-readable summary of review findings.

    Args:
        findings: Parsed findings list from parse_findings().
        file_path: Optional file path to include in the header.
    """
    if not findings:
        header = f"OK — no review findings.{' (' + file_path + ')' if file_path else ''}"
        return header

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1

    dist = "  ".join(f"{sev}={counts[sev]}" for sev in [s.value for s in SEVERITY_ORDER] if sev in counts)
    header = f"Review findings{' — ' + file_path if file_path else ''}: {len(findings)} total  [{dist}]"

    sections: list[str] = [header, ""]
    for finding in findings:
        sections.append(finding.format())
        sections.append("")

    return "\n".join(sections).rstrip()


def format_findings_text(findings: list[Finding]) -> str:
    """Return findings as plain structured text, one per block."""
    return "\n\n".join(f.format() for f in findings)


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    """Return a dict of severity label → count."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    return counts


def has_blocking_findings(findings: list[Finding]) -> bool:
    """Return True if any finding is CRITICAL, RISK, ARCHITECTURE, or WARNING severity."""
    blocking = {Severity.CRITICAL, Severity.RISK, Severity.ARCHITECTURE, Severity.WARNING}
    return any(f.severity in blocking for f in findings)


if __name__ == "__main__":
    import sys

    sample = """
[WARNING] mq-mcp/bridge.py:270
show_bridget_face opens /dev/tty but does not use try/finally.

[MISSING] mq-mcp/bridge.py:76
scramble_print has no docstring.

[NOTE] mq-mcp/bridge.py:339
The CD: comment explains a real shell constraint — keep it.

[SUGGESTION] mq-mcp/bridge.py:302
known_local_repos imports Path locally despite a module-level import.
"""

    findings = parse_findings(sample)
    print(format_summary(findings, "mq-mcp/bridge.py"))
    print()
    print(f"Blocking: {has_blocking_findings(findings)}")
    print(f"Counts:   {severity_counts(findings)}")

    sys.exit(0)
