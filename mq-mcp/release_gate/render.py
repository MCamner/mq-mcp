"""Human rendering for Release Gate v2."""
from __future__ import annotations

from .models import ReleaseGateResult


def render_release_gate(result: ReleaseGateResult) -> str:
    lines = [
        "MQ RELEASE GATE V2",
        "",
        f"Repo: {result.repo}",
        f"Target: {result.target}",
        f"Status: {result.status.upper()}",
        f"Score: {result.score}",
        "",
        "Blockers:",
    ]
    lines.extend(_numbered(result.blockers))
    lines.append("")
    lines.append("Warnings:")
    lines.extend(_numbered(result.warnings))
    lines.append("")
    lines.append("Next actions:")
    lines.extend(_numbered(result.next_actions))
    return "\n".join(lines)


def _numbered(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"{index}. {item}" for index, item in enumerate(items, start=1)]
