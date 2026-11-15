"""Bridget workflow entrypoint (Phase 8).

Gives Bridget a thin ``bridget --workflow "..."`` surface that *delegates* to
``mq-agent workflow``, or to one of three read-only mq-agent commands
(``SHORTCUTS``) run with an argv Bridget builds and never widens. Bridget may extract the goal, identify the repo, propose a
known template, ask mq-agent to plan, present the plan, and — after explicit
approval — ask mq-agent to run it and present the result.

Bridget owns no orchestration here: it holds no run state, implements no retry,
writes no workflow state, builds no free shell chains, and never selects tools or
bypasses tool policy. All of that lives in mq-agent (orchestration) and mq-mcp's
MCP surface (execution).

Boundary recursion guards:
  * refuse to start a workflow when ``MQ_WORKFLOW_DEPTH`` is already set (deny
    nested workflow start and Bridget calling itself);
  * set ``MQ_WORKFLOW_DEPTH=1`` in the mq-agent child env so anything downstream
    that tries to start another workflow is denied too.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

#: The fixed, known workflow templates (must match mq-agent's template set).
KNOWN_TEMPLATES: tuple[str, ...] = (
    "repo-preflight",
    "review-and-test",
    "release-ready",
)

#: Deterministic keyword → template map. v1 routing for three fixed outcomes.
#: On no match OR an ambiguous match (keywords for more than one template) we do
#: NOT guess — the caller lists the templates and asks the user to choose.
_TEMPLATE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "repo-preflight": (
        "preflight", "pre-flight", "doctor", "selftest", "self-test",
        "self test", "health", "healthy", "sanity", "before push",
        "before i push", "before commit",
    ),
    "review-and-test": (
        "review", "diff", "lint", "code review", "unit test", "run tests",
        "run the tests", "test this", "testing",
    ),
    "release-ready": (
        "release", "ship", "shipping", "publish", "ready to ship",
        "ready to release", "release-ready", "release ready", "tag a release",
    ),
}


#: Read-only mq-agent commands Bridget can run directly, beside the workflow
#: templates. Bridget builds their argv in ``shortcut_argv`` and never adds a
#: write flag: ``fix-ci`` stays a diagnosis and ``pr review`` stays local.
SHORTCUTS: tuple[str, ...] = ("ci-diagnose", "stack-status", "pr-review")

_SHORTCUT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ci-diagnose": (
        "ci fail", "ci is failing", "failing ci", "ci is red", "red ci",
        "fix ci", "fix-ci", "ci error", "broken ci", "ci broke", "build failed",
        "build is failing", "ci fallerar", "ci är röd", "röd ci", "ci-fel",
    ),
    "stack-status": (
        "stack status", "stack health", "status of the stack", "state of the stack",
        "stackstatus", "stackens status", "status på stacken",
    ),
    "pr-review": (
        "review pr", "pr review", "review pull request", "review the pr",
        "granska pr", "granska pull request",
    ),
}

#: Every intent Bridget can propose, in picker order.
KNOWN_INTENTS: tuple[str, ...] = (*KNOWN_TEMPLATES, *SHORTCUTS)

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {**_TEMPLATE_KEYWORDS, **_SHORTCUT_KEYWORDS}


def classify_goal(goal: str) -> str | None:
    """Map a free-text goal to one known intent, or None when uncertain.

    Returns the intent only when exactly one matches. A match whose every
    keyword lies inside a longer keyword matched for another intent is dropped
    first: "stack health" is stack-status, not repo-preflight's "health", and
    "review pr 12" is pr-review, not review-and-test's "review". Zero matches
    or independent matches for more than one intent return None so the caller
    can ask the user to choose rather than guess.
    """
    text = (goal or "").lower()
    matched = {
        intent: [kw for kw in keywords if kw in text]
        for intent, keywords in _INTENT_KEYWORDS.items()
    }
    matched = {intent: kws for intent, kws in matched.items() if kws}

    def _covered(intent: str) -> bool:
        longer = [kw for other, kws in matched.items() if other != intent for kw in kws]
        return all(any(kw in big and kw != big for big in longer) for kw in matched[intent])

    remaining = [intent for intent in matched if not _covered(intent)]
    if len(remaining) == 1:
        return remaining[0]
    return None


_PR_NUMBER = re.compile(r"(?:#|\bpr\s*#?|pull request\s*#?)(\d+)", re.IGNORECASE)


def pr_number(goal: str) -> int | None:
    """The PR number named in the goal ("pr 12", "PR #12", "pull request 12")."""
    match = _PR_NUMBER.search(goal or "")
    return int(match.group(1)) if match else None


def shortcut_argv(name: str, repo: Path, number: int | None) -> list[str]:
    """The exact mq-agent argv for a shortcut. Never includes a write flag."""
    if name == "ci-diagnose":
        return ["fix-ci", str(repo)]
    if name == "stack-status":
        return ["stack", "status"]
    if name == "pr-review":
        if number is None:
            raise ValueError("pr-review needs a PR number")
        return ["pr", "review", str(number), "--repo", str(repo)]
    raise ValueError(f"unknown shortcut: {name}")


def identify_repo(goal: str, cwd: Path | None = None) -> Path:
    """Resolve the target repo: an explicit path token in the goal wins, else cwd."""
    cwd = cwd or Path.cwd()
    for token in (goal or "").split():
        if token.startswith(("/", "~", "./")) or "/" in token:
            candidate = Path(token).expanduser()
            if candidate.is_dir():
                return candidate.resolve()
    return cwd.resolve()


def _mq_agent_home() -> Path:
    home = (
        os.environ.get("MQ_AGENT_HOME")
        or os.environ.get("MQ_AGENT_BIN")
        or str(Path.home() / "mq-agent")
    )
    return Path(home).expanduser()


def _invoke_mq_agent(args: list[str], *, capture: bool = True) -> tuple[str, int]:
    """Run ``mq-agent <args>`` in the mq-agent project, with the depth guard set.

    When capture is True the child's combined output is returned for parsing.
    When False the child inherits this process's stdio so progress and any
    interactive prompts reach the terminal live. Returns (output, returncode).
    A missing mq-agent install is reported as a clear optional-dependency error
    rather than crashing.
    """
    home = _mq_agent_home()
    if not home.is_dir():
        return (f"ERROR: mq-agent not found at {home}. Set MQ_AGENT_HOME.", 127)

    env = {**os.environ, "MQ_WORKFLOW_DEPTH": "1", "UV_NO_CONFIG": "1"}
    env.pop("VIRTUAL_ENV", None)
    cmd = ["uv", "--project", str(home), "run", "mq-agent", *args]
    try:
        if capture:
            result = subprocess.run(
                cmd, cwd=str(home), env=env,
                capture_output=True, text=True, timeout=120,
            )
            return ((result.stdout + result.stderr).strip(), result.returncode)
        result = subprocess.run(cmd, cwd=str(home), env=env)
        return ("", result.returncode)
    except FileNotFoundError:
        return ("ERROR: 'uv' not found on PATH; cannot reach mq-agent.", 127)
    except subprocess.TimeoutExpired:
        return ("ERROR: mq-agent workflow timed out.", 1)


def _read_line(prompt: str) -> str:
    """Read one line from the terminal (/dev/tty), falling back to stdin.

    Returns "" when there is no interactive terminal so callers fail closed
    (no run, no guess) instead of blocking.
    """
    try:
        with open("/dev/tty", "r+") as tty:
            tty.write(prompt)
            tty.flush()
            return (tty.readline() or "").strip()
    except OSError:
        if sys.stdin and sys.stdin.isatty():
            try:
                return input(prompt).strip()
            except EOFError:
                return ""
        return ""


def _choose_template() -> str | None:
    """Ask the user to pick one known intent. None if not chosen."""
    print("Could not map that goal to a known workflow or shortcut. Choose one:")
    for i, name in enumerate(KNOWN_INTENTS, 1):
        print(f"  {i}. {name}")
    answer = _read_line("Number (or blank to cancel): ")
    if answer.isdigit() and 1 <= int(answer) <= len(KNOWN_INTENTS):
        return KNOWN_INTENTS[int(answer) - 1]
    if answer in KNOWN_INTENTS:
        return answer
    return None


def _run_shortcut(
    name: str,
    goal: str,
    repo: Path,
    *,
    assume_yes: bool,
    on_delegated: Callable[[str, str, int], None] | None,
) -> int:
    """Show the exact read-only command, confirm, then delegate it to mq-agent."""
    number = pr_number(goal) if name == "pr-review" else None
    if name == "pr-review" and number is None:
        answer = _read_line("PR number (or blank to cancel): ")
        if not answer.lstrip("#").isdigit():
            print("No PR number given. Nothing to do.")
            return 0
        number = int(answer.lstrip("#"))
    args = shortcut_argv(name, repo, number)
    print(f"Shortcut: {name}\n  mq-agent {' '.join(args)}")

    if not assume_yes:
        answer = _read_line(f"\nRun '{name}'? [y/N] ").lower()
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return 0

    _, rc = _invoke_mq_agent(args, capture=False)
    if on_delegated is not None:
        on_delegated(goal, name, rc)
    return rc


def _format_plan(plan_json: str) -> str:
    """Render the mq-agent plan JSON as a short, readable summary."""
    try:
        plan = json.loads(plan_json)
    except (ValueError, TypeError):
        return plan_json
    steps = plan.get("steps", [])
    lines = [f"Plan: {plan.get('template', '?')} on {plan.get('repo', '?')}"]
    for step in steps:
        tool = step.get("tool", "?")
        sid = step.get("id", "?")
        lines.append(f"  - {sid}: {tool}")
    return "\n".join(lines)


def run_workflow_entry(
    goal: str,
    *,
    assume_yes: bool = False,
    on_delegated: Callable[[str, str, int], None] | None = None,
) -> int:
    """Propose a template, show its plan, confirm, then delegate the run.

    Returns a process exit code. Never persists run state or retries.
    ``on_delegated(goal, template, rc)`` is called once the run was handed to
    mq-agent, so the caller can record the delegation.
    """
    # Recursion guard: deny nested workflow start / Bridget calling itself.
    if os.environ.get("MQ_WORKFLOW_DEPTH"):
        print(
            "ERROR: refusing to start a workflow from inside a workflow "
            "(MQ_WORKFLOW_DEPTH is set).",
            file=sys.stderr,
        )
        return 1

    if not (goal or "").strip():
        print('ERROR: no goal given. Usage: bridget --workflow "your goal"', file=sys.stderr)
        return 1

    template = classify_goal(goal)
    if template is None:
        template = _choose_template()
        if template is None:
            print("No template selected. Nothing to do.")
            return 0

    repo = identify_repo(goal)

    if template in SHORTCUTS:
        return _run_shortcut(
            template, goal, repo, assume_yes=assume_yes, on_delegated=on_delegated,
        )

    plan_out, plan_rc = _invoke_mq_agent(
        ["workflow", "plan", template, "--repo", str(repo)]
    )
    if plan_rc != 0:
        print(plan_out, file=sys.stderr)
        return plan_rc
    print(_format_plan(plan_out))

    if not assume_yes:
        answer = _read_line(f"\nRun '{template}' on {repo}? [y/N] ").lower()
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return 0

    # Bridget's y/N is the start gate; pass --yes so mq-agent does not re-prompt
    # for the same plan. The Runner's per-tool policy gates are unaffected.
    _, run_rc = _invoke_mq_agent(
        ["workflow", "run", template, "--repo", str(repo), "--yes"],
        capture=False,
    )
    if on_delegated is not None:
        on_delegated(goal, template, run_rc)
    return run_rc
