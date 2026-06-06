"""Release Gate v2 runner."""
from __future__ import annotations

from pathlib import Path

from .checks import run_p0_checks
from .models import GateCheck, ReleaseGateResult


def _score(checks: list[GateCheck]) -> int:
    if not checks:
        return 0
    blocked = sum(1 for check in checks if check.status == "blocked")
    warnings = sum(1 for check in checks if check.status == "warning")
    return max(0, 100 - blocked * 18 - warnings * 7)


def run_release_gate(repo: str | Path, target: str, test_command: list[str] | None = None) -> ReleaseGateResult:
    repo_path = Path(repo).expanduser().resolve()
    checks = run_p0_checks(repo_path, target, test_command=test_command)
    blockers = [check.message for check in checks if check.status == "blocked" or check.blocker]
    warnings = [check.message for check in checks if check.status == "warning" and not check.blocker]
    next_actions = []
    for check in checks:
        if check.next_action and check.next_action not in next_actions:
            next_actions.append(check.next_action)
    status = "blocked" if blockers else "warning" if warnings else "pass"
    return ReleaseGateResult(
        repo=repo_path.name,
        target=target,
        status=status,
        score=_score(checks),
        blockers=blockers,
        warnings=warnings,
        next_actions=next_actions,
        checks=checks,
    )
