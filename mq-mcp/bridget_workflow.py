"""Bridget workflow entrypoint (Phase 8).

Gives Bridget a thin ``bridget --workflow "..."`` surface that *delegates* to
``mq-agent workflow``. Bridget may extract the goal, identify the repo, propose a
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
import subprocess
import sys
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


def classify_goal(goal: str) -> str | None:
    """Map a free-text goal to one known template, or None when uncertain.

    Returns the template name only when exactly one template's keywords match.
    Zero matches or matches spanning more than one template return None so the
    caller can ask the user to choose rather than guess.
    """
    text = (goal or "").lower()
    matched = {
        template
        for template, keywords in _TEMPLATE_KEYWORDS.items()
        if any(kw in text for kw in keywords)
    }
    if len(matched) == 1:
        return next(iter(matched))
    return None


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
    """Ask the user to pick one of the known templates. None if not chosen."""
    print("Could not map that goal to a known workflow. Choose one:")
    for i, name in enumerate(KNOWN_TEMPLATES, 1):
        print(f"  {i}. {name}")
    answer = _read_line("Template number (or blank to cancel): ")
    if answer.isdigit() and 1 <= int(answer) <= len(KNOWN_TEMPLATES):
        return KNOWN_TEMPLATES[int(answer) - 1]
    if answer in KNOWN_TEMPLATES:
        return answer
    return None


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


def run_workflow_entry(goal: str, *, assume_yes: bool = False) -> int:
    """Propose a template, show its plan, confirm, then delegate the run.

    Returns a process exit code. Never persists run state or retries.
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
    return run_rc
