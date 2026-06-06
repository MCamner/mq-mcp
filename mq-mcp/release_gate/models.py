"""Release Gate v2 data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReleaseGateStatus = Literal["pass", "warning", "blocked"]


@dataclass(frozen=True)
class GateCheck:
    """One deterministic release readiness check."""

    name: str
    status: ReleaseGateStatus
    message: str
    blocker: bool = False
    next_action: str | None = None


@dataclass(frozen=True)
class ReleaseGateResult:
    """Machine-readable Release Gate v2 result."""

    repo: str
    target: str
    status: ReleaseGateStatus
    score: int
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    checks: list[GateCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "repo": self.repo,
            "target": self.target,
            "status": self.status,
            "score": self.score,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "next_actions": self.next_actions,
            "checks": [check.__dict__ for check in self.checks],
        }
