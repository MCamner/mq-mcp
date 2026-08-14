"""Read-only CodeGraph symbol lookup for Bridget's synchronous CLI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import bridget_runtime

CODEGRAPH_TIMEOUT = 20


def parse_symbol_args(argv: list[str]) -> tuple[str, str | None, str | None]:
    """Parse ``--symbol NAME [--repo REPO] [--file PATH]`` strictly."""
    if not argv or argv[0] != "--symbol" or len(argv) < 2 or argv[1].startswith("-"):
        raise ValueError("usage: bridget --symbol NAME [--repo REPO] [--file PATH]")
    symbol = argv[1]
    values: dict[str, str | None] = {"--repo": None, "--file": None}
    index = 2
    while index < len(argv):
        flag = argv[index]
        if flag not in values or values[flag] is not None:
            raise ValueError("usage: bridget --symbol NAME [--repo REPO] [--file PATH]")
        if index + 1 >= len(argv) or argv[index + 1].startswith("-"):
            raise ValueError(f"{flag} requires a value")
        values[flag] = argv[index + 1]
        index += 2
    return symbol, values["--repo"], values["--file"]


def parse_dependency_args(
    argv: list[str],
) -> tuple[str, str | None, str, int]:
    """Parse bounded callers/callees lookup arguments strictly."""
    usage = (
        "usage: bridget --dependencies NAME [--repo REPO] "
        "[--direction callers|callees|both] [--limit 1-100]"
    )
    if not argv or argv[0] != "--dependencies" or len(argv) < 2 or argv[1].startswith("-"):
        raise ValueError(usage)
    symbol = argv[1]
    values: dict[str, str | None] = {
        "--repo": None,
        "--direction": None,
        "--limit": None,
    }
    index = 2
    while index < len(argv):
        flag = argv[index]
        if flag not in values or values[flag] is not None:
            raise ValueError(usage)
        if index + 1 >= len(argv) or argv[index + 1].startswith("-"):
            raise ValueError(f"{flag} requires a value")
        values[flag] = argv[index + 1]
        index += 2

    direction = values["--direction"] or "both"
    if direction not in {"callers", "callees", "both"}:
        raise ValueError("--direction must be callers, callees, or both")
    raw_limit = values["--limit"] or "20"
    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise ValueError("--limit must be an integer from 1 to 100") from exc
    if not 1 <= limit <= 100:
        raise ValueError("--limit must be an integer from 1 to 100")
    return symbol, values["--repo"], direction, limit


def resolve_repo(target: str | None) -> Path | None:
    """Resolve an explicit, pinned, or current Git repository."""
    if target:
        repos = bridget_runtime.known_local_repos()
        match = next((name for name in repos if name.lower() == target.lower()), None)
        candidate = Path(repos[match]) if match else Path(target).expanduser()
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        return resolved if resolved.is_dir() else None

    project = bridget_runtime.get_project()
    if project and project.get("path"):
        candidate = Path(str(project["path"])).expanduser()
        if candidate.is_dir():
            return candidate.resolve()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    candidate = Path(result.stdout.strip())
    return candidate.resolve() if candidate.is_dir() else None


def handle_symbol(
    symbol: str,
    *,
    repo: str | None = None,
    file_path: str | None = None,
) -> int:
    """Delegate one symbol lookup to CodeGraph and preserve its output contract."""
    repo_path = resolve_repo(repo)
    if repo_path is None:
        print("ERROR: repository not found; use --repo REPO or pin a project", file=sys.stderr)
        return 2
    executable = shutil.which("codegraph")
    if executable is None:
        print("ERROR: codegraph is not installed or not on PATH", file=sys.stderr)
        return 127

    command = [executable, "--no-color", "node", "--path", str(repo_path)]
    if file_path:
        command.extend(["--file", file_path])
    command.append(symbol)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=CODEGRAPH_TIMEOUT,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: CodeGraph lookup timed out after {CODEGRAPH_TIMEOUT}s", file=sys.stderr)
        return 124
    except OSError as exc:
        print(f"ERROR: could not run CodeGraph: {exc}", file=sys.stderr)
        return 1

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def handle_dependencies(
    symbol: str,
    *,
    repo: str | None = None,
    direction: str = "both",
    limit: int = 20,
) -> int:
    """Print bounded callers and/or callees using supported CodeGraph commands."""
    repo_path = resolve_repo(repo)
    if repo_path is None:
        print("ERROR: repository not found; use --repo REPO or pin a project", file=sys.stderr)
        return 2
    executable = shutil.which("codegraph")
    if executable is None:
        print("ERROR: codegraph is not installed or not on PATH", file=sys.stderr)
        return 127

    queries = [direction] if direction != "both" else ["callers", "callees"]
    for query in queries:
        command = [
            executable,
            "--no-color",
            query,
            "--path",
            str(repo_path),
            "--limit",
            str(limit),
            symbol,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=CODEGRAPH_TIMEOUT,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            print(f"ERROR: CodeGraph lookup timed out after {CODEGRAPH_TIMEOUT}s", file=sys.stderr)
            return 124
        except OSError as exc:
            print(f"ERROR: could not run CodeGraph: {exc}", file=sys.stderr)
            return 1

        heading = "Callers" if query == "callers" else "Callees"
        sys.stdout.write(f"## {heading} of {symbol}\n")
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        if result.returncode != 0:
            return result.returncode
    return 0


def maybe_handle_symbol(argv: list[str]) -> int | None:
    """Return a command exit code when ``--symbol`` is selected, else None."""
    if not argv or argv[0] != "--symbol":
        return None
    try:
        symbol, repo, file_path = parse_symbol_args(argv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return handle_symbol(symbol, repo=repo, file_path=file_path)


def maybe_handle_lookup(argv: list[str]) -> int | None:
    """Dispatch Bridget's supported CodeGraph lookup commands."""
    symbol_result = maybe_handle_symbol(argv)
    if symbol_result is not None:
        return symbol_result
    if not argv or argv[0] != "--dependencies":
        return None
    try:
        symbol, repo, direction, limit = parse_dependency_args(argv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return handle_dependencies(
        symbol,
        repo=repo,
        direction=direction,
        limit=limit,
    )
