"""Small local CLI for mq-mcp install and runtime workflows."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
VERSION_FILE = REPO_ROOT / "VERSION"
PYPROJECT_FILE = APP_DIR / "pyproject.toml"
ENV_FILE = APP_DIR / ".env"
ENV_EXAMPLE_FILE = APP_DIR / ".env.example"
CONTRACTS_FILE = REPO_ROOT / "docs" / "tool_contracts.json"
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validate.sh"
PROFILES_DIR = REPO_ROOT / "profiles"
STABILITY_FILE = REPO_ROOT / "docs" / "stability.json"


def read_version() -> str:
    # Source checkouts read the repo VERSION file. Wheel/sdist installs do not
    # ship the root VERSION file, so fall back to installed package metadata
    # rather than crashing on a missing file.
    if VERSION_FILE.is_file():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("mq-mcp")
    except PackageNotFoundError:
        return "unknown"
    except Exception:
        return "unknown"


def run_command(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(args, cwd=cwd, env=merged_env, check=False).returncode


def capture_command(args: list[str], cwd: Path, timeout: int = 90) -> dict[str, object]:
    started = time.time()
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout + result.stderr)[-12000:]
        return {
            "args": args,
            "returncode": result.returncode,
            "elapsed_ms": round((time.time() - started) * 1000, 2),
            "output_tail": output,
        }
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or ""))[-12000:]
        return {
            "args": args,
            "returncode": 124,
            "elapsed_ms": round((time.time() - started) * 1000, 2),
            "output_tail": output,
            "error": "timeout",
        }


def safe_git_summary() -> dict[str, object]:
    branch = capture_command(["git", "branch", "--show-current"], REPO_ROOT, timeout=10)
    status = capture_command(["git", "status", "--short", "--branch"], REPO_ROOT, timeout=10)
    commit = capture_command(["git", "log", "-1", "--oneline"], REPO_ROOT, timeout=10)
    return {
        "branch": str(branch.get("output_tail", "")).strip(),
        "status": str(status.get("output_tail", "")).strip().splitlines(),
        "latest_commit": str(commit.get("output_tail", "")).strip(),
    }


def redacted_env_summary() -> dict[str, object]:
    keys = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "MQ_MCP_HOST",
        "MQ_MCP_PORT",
        "MQ_MCP_ALLOWED_PATHS",
        "MQ_MCP_LOCAL_REPOS",
        "MQ_MCP_REQUEST_LOG",
    ]
    secret_markers = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    summary: dict[str, object] = {}
    for key in keys:
        value = os.getenv(key)
        if value is None:
            summary[key] = {"set": False}
        elif any(marker in key for marker in secret_markers):
            summary[key] = {"set": True, "value": "<redacted>"}
        else:
            summary[key] = {"set": True, "value": value}
    return summary


def load_contract_summary() -> dict[str, object]:
    try:
        data = json.loads(CONTRACTS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    classes: dict[str, int] = {}
    for tool in data.get("tools", []):
        safety_class = str(tool.get("class", "unknown"))
        classes[safety_class] = classes.get(safety_class, 0) + 1
    return {
        "ok": True,
        "schema_version": data.get("schema_version"),
        "version": data.get("mq_mcp_version"),
        "tool_count": data.get("tool_count"),
        "safety_classes": classes,
    }


def load_profiles() -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = str(path)
        profiles.append(data)
    return profiles


def find_profile(name: str) -> dict[str, object] | None:
    for profile in load_profiles():
        if profile.get("name") == name:
            return profile
    return None


def load_stability() -> dict[str, object]:
    return json.loads(STABILITY_FILE.read_text(encoding="utf-8"))


def build_health_payload() -> dict[str, object]:
    contracts = load_contract_summary()
    return {
        "name": "mq-mcp",
        "version": read_version() if VERSION_FILE.is_file() else "unknown",
        "status": "ok" if contracts.get("ok") else "degraded",
        "repo_root": str(REPO_ROOT),
        "config_path": str(ENV_FILE),
        "tool_count": contracts.get("tool_count"),
        "contracts_ok": contracts.get("ok", False),
    }


def build_report(run_validation: bool = False) -> dict[str, object]:
    started = time.time()
    report: dict[str, object] = {
        "name": "mq-mcp",
        "version": read_version() if VERSION_FILE.is_file() else "unknown",
        "generated_at_unix": round(started, 3),
        "health": build_health_payload(),
        "contracts": load_contract_summary(),
        "git": safe_git_summary(),
        "env": redacted_env_summary(),
        "paths": {
            "repo_root": str(REPO_ROOT),
            "app_dir": str(APP_DIR),
            "config_path": str(ENV_FILE),
            "contracts": str(CONTRACTS_FILE),
            "validate_script": str(VALIDATE_SCRIPT),
        },
    }
    if run_validation:
        report["validation"] = capture_command([str(VALIDATE_SCRIPT)], REPO_ROOT, timeout=120)
    report["elapsed_ms"] = round((time.time() - started) * 1000, 2)
    return report


def print_payload(payload: dict[str, object], json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"mq-mcp {payload.get('version', 'unknown')}")
    print(f"status: {payload.get('status', 'ok')}")
    print(f"repo:   {payload.get('repo_root', REPO_ROOT)}")
    if "tool_count" in payload:
        print(f"tools:  {payload.get('tool_count')}")


def doctor(json_output: bool = False) -> int:
    checks = [
        ("version_file", VERSION_FILE.is_file(), str(VERSION_FILE)),
        ("pyproject", PYPROJECT_FILE.is_file(), str(PYPROJECT_FILE)),
        ("server", (APP_DIR / "server.py").is_file(), str(APP_DIR / "server.py")),
        ("bridge", (APP_DIR / "bridge.py").is_file(), str(APP_DIR / "bridge.py")),
        ("env_example", ENV_EXAMPLE_FILE.is_file(), str(ENV_EXAMPLE_FILE)),
        ("validate_script", (REPO_ROOT / "scripts" / "validate.sh").is_file(), str(REPO_ROOT / "scripts" / "validate.sh")),
        ("tool_contracts", (REPO_ROOT / "docs" / "tool_contracts.json").is_file(), str(REPO_ROOT / "docs" / "tool_contracts.json")),
        ("uv_available", shutil.which("uv") is not None, shutil.which("uv") or "uv not found"),
        ("git_available", shutil.which("git") is not None, shutil.which("git") or "git not found"),
    ]
    optional = [
        ("env_file", ENV_FILE.is_file(), str(ENV_FILE)),
        ("openai_api_key", bool(os.getenv("OPENAI_API_KEY")), "set in environment or .env for bridge prompts"),
    ]

    required_ok = all(ok for _, ok, _ in checks)
    payload = {
        "name": "mq-mcp",
        "version": read_version() if VERSION_FILE.is_file() else "unknown",
        "repo_root": str(REPO_ROOT),
        "app_dir": str(APP_DIR),
        "config_path": str(ENV_FILE),
        "status": "ok" if required_ok else "failed",
        "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks],
        "optional": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in optional],
    }

    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mq-mcp {payload['version']}")
        print(f"repo:   {REPO_ROOT}")
        print(f"config: {ENV_FILE}")
        for item in payload["checks"]:
            status = "OK" if item["ok"] else "FAIL"
            print(f"{status:4} {item['name']}: {item['detail']}")
        for item in payload["optional"]:
            status = "OK" if item["ok"] else "SKIP"
            print(f"{status:4} {item['name']}: {item['detail']}")

    return 0 if required_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mq-mcp",
        description="Local mq-mcp install, validation, and server helper.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Print the mq-mcp version.")

    doctor_parser = sub.add_parser("doctor", help="Check local install readiness.")
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable status.")

    health_parser = sub.add_parser("health", help="Print local health summary.")
    health_parser.add_argument("--json", action="store_true", help="Print machine-readable status.")

    info_parser = sub.add_parser("info", help="Print local server and tool metadata.")
    info_parser.add_argument("--json", action="store_true", help="Print machine-readable status.")

    report_parser = sub.add_parser("report", help="Print redacted diagnostics report.")
    report_parser.add_argument("--json", action="store_true", help="Print machine-readable status.")
    report_parser.add_argument("--validate", action="store_true", help="Include validation output.")

    bundle_parser = sub.add_parser("bundle", help="Write a redacted troubleshooting JSON bundle.")
    bundle_parser.add_argument("--validate", action="store_true", help="Include validation output.")

    serve_parser = sub.add_parser("serve", help="Run the local MCP server.")
    serve_parser.add_argument("--host", help="Override MQ_MCP_HOST for HTTP/SSE transports.")
    serve_parser.add_argument("--port", help="Override MQ_MCP_PORT for HTTP/SSE transports.")

    sub.add_parser("validate", help="Run scripts/validate.sh from the repository root.")

    tools_parser = sub.add_parser("tools", help="List tools exposed through bridge.py or the registry.")
    tools_parser.add_argument("--json", action="store_true", help="Print full tool index as JSON.")
    tools_parser.add_argument("--safety", action="store_true", help="Print safety-focused tool view as JSON.")
    tools_parser.add_argument("--markdown", action="store_true", help="Print tool index as a Markdown table.")
    tools_parser.add_argument("--export", action="store_true", help="Write generated/tool-index.json, tool-safety.json, runtime-contract.json.")

    profiles_parser = sub.add_parser("profiles", help="Inspect MCP profile templates.")
    profiles_sub = profiles_parser.add_subparsers(dest="profiles_command")
    profiles_sub.add_parser("list", help="List available profile templates.")
    show_parser = profiles_sub.add_parser("show", help="Show one profile template.")
    show_parser.add_argument("name", help="Profile name, e.g. read-only or claude-desktop.")
    profiles_sub.add_parser("path", help="Print the profiles directory.")
    profiles_sub.add_parser("validate", help="Validate profile templates.")

    stability_parser = sub.add_parser("stability", help="Inspect the v1 stability baseline.")
    stability_sub = stability_parser.add_subparsers(dest="stability_command")
    stability_sub.add_parser("show", help="Show stability baseline JSON.")
    stability_sub.add_parser("validate", help="Validate stability baseline.")

    config_parser = sub.add_parser("config", help="Inspect local config paths.")
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_sub.add_parser("path", help="Print the .env path.")
    config_sub.add_parser("example", help="Print the .env.example path.")
    config_sub.add_parser("root", help="Print the repository root path.")

    memory_parser = sub.add_parser("memory", help="Inspect and audit semantic memory.")
    memory_sub = memory_parser.add_subparsers(dest="memory_command")
    memory_sub.add_parser("audit", help="Audit semantic memory for policy compliance.")
    memory_sub.add_parser("count", help="Print number of entries in the store.")
    memory_list = memory_sub.add_parser("list", help="List all semantic memory entries.")
    memory_list.add_argument("--json", action="store_true", help="Output as JSON.")

    release_gate_parser = sub.add_parser("release-gate", help="Run Release Gate v2.")
    release_gate_sub = release_gate_parser.add_subparsers(dest="release_gate_command")
    release_gate_run = release_gate_sub.add_parser("run", help="Run deterministic release checks.")
    release_gate_run.add_argument("--repo", default=".", help="Repository path to validate.")
    release_gate_run.add_argument("--target", required=True, help="Target release, e.g. v1.4.0.")
    release_gate_run.add_argument("--json", action="store_true", help="Print machine-readable output.")
    release_gate_run.add_argument(
        "--test-command",
        help="Optional shell-style test command to run, e.g. 'python -m pytest -q'.",
    )
    release_gate_run.add_argument(
        "--lint-command",
        help="Optional shell-style lint/type command to run, e.g. 'ruff check . && mypy .'.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(read_version())
        return 0
    if args.command == "doctor":
        return doctor(json_output=args.json)
    if args.command == "health":
        print_payload(build_health_payload(), json_output=args.json)
        return 0
    if args.command == "info":
        payload = build_report(run_validation=False)
        summary = {
            "name": payload["name"],
            "version": payload["version"],
            "status": payload["health"]["status"],  # type: ignore[index]
            "repo_root": str(REPO_ROOT),
            "tool_count": payload["contracts"].get("tool_count"),  # type: ignore[union-attr]
            "safety_classes": payload["contracts"].get("safety_classes"),  # type: ignore[union-attr]
            "git": payload["git"],
        }
        print_payload(summary, json_output=args.json)
        return 0
    if args.command == "report":
        payload = build_report(run_validation=args.validate)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            health = payload["health"]
            contracts = payload["contracts"]
            print(f"mq-mcp {payload['version']}")
            print(f"status: {health['status']}")  # type: ignore[index]
            print(f"tools:  {contracts.get('tool_count')}")  # type: ignore[union-attr]
            print(f"repo:   {REPO_ROOT}")
            print(f"config: {ENV_FILE}")
            if args.validate:
                validation = payload.get("validation", {})
                print(f"validation_returncode: {validation.get('returncode')}")
        return 0
    if args.command == "bundle":
        payload = build_report(run_validation=args.validate)
        fd, path = tempfile.mkstemp(prefix="mq-mcp-report-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(path)
        return 0
    if args.command == "serve":
        env: dict[str, str] = {}
        if args.host:
            env["MQ_MCP_HOST"] = args.host
        if args.port:
            env["MQ_MCP_PORT"] = args.port
        env["MQ_MCP_TRANSPORT"] = "sse"
        return run_command(["uv", "run", "python", "server.py"], APP_DIR, env)
    if args.command == "validate":
        return run_command([str(REPO_ROOT / "scripts" / "validate.sh")], REPO_ROOT)
    if args.command == "tools":
        if args.json or args.safety or args.markdown or args.export:
            from tool_registry import (  # noqa: PLC0415
                as_markdown_table,
                export_runtime_contract,
                export_tool_index,
                export_tool_safety,
                load_registry,
                registry_summary,
            )
            if args.json:
                import json as _json
                summary = registry_summary()
                payload = {**summary, "tools": load_registry()}
                print(_json.dumps(payload, indent=2))
                return 0
            if args.safety:
                import json as _json
                from pathlib import Path as _Path
                out = export_tool_safety(_Path("/dev/stdout"))
                return 0
            if args.markdown:
                print(as_markdown_table())
                return 0
            if args.export:
                from tool_registry import (  # noqa: PLC0415
                    export_profile_index,
                    export_release_state,
                )
                from tool_policy import export_tool_policies  # noqa: PLC0415
                idx = export_tool_index()
                saf = export_tool_safety()
                rc = export_runtime_contract()
                rs = export_release_state()
                pi = export_profile_index()
                tp = export_tool_policies()
                for p in (idx, saf, rc, rs, pi, tp):
                    print(f"written: {p.relative_to(REPO_ROOT)}")
                return 0
        return run_command(["uv", "run", "python", "bridge.py", "--tools"], APP_DIR)
    if args.command == "profiles":
        if args.profiles_command == "list":
            for profile in load_profiles():
                print(f"{profile['name']}\t{profile['title']}")
            return 0
        if args.profiles_command == "show":
            profile = find_profile(args.name)
            if profile is None:
                print(f"ERROR: unknown profile: {args.name}", file=sys.stderr)
                return 1
            print(json.dumps(profile, indent=2, sort_keys=True))
            return 0
        if args.profiles_command == "path":
            print(PROFILES_DIR)
            return 0
        if args.profiles_command == "validate":
            return run_command([str(REPO_ROOT / "scripts" / "check-profiles.py")], REPO_ROOT)
        parser.error("profiles requires one of: list, show, path, validate")
    if args.command == "stability":
        if args.stability_command == "show":
            print(json.dumps(load_stability(), indent=2, sort_keys=True))
            return 0
        if args.stability_command == "validate":
            return run_command([str(REPO_ROOT / "scripts" / "check-stability.py")], REPO_ROOT)
        parser.error("stability requires one of: show, validate")
    if args.command == "config":
        if args.config_command == "path":
            print(ENV_FILE)
            return 0
        if args.config_command == "example":
            print(ENV_EXAMPLE_FILE)
            return 0
        if args.config_command == "root":
            print(REPO_ROOT)
            return 0
        parser.error("config requires one of: path, example, root")
    if args.command == "memory":
        store_path = REPO_ROOT / "semantic_memory" / "store.json"
        if args.memory_command == "audit":
            return run_command(
                [str(REPO_ROOT / "scripts" / "check-semantic-memory.sh")], REPO_ROOT
            )
        if args.memory_command == "count":
            if not store_path.exists():
                print("0")
                return 0
            data = json.loads(store_path.read_text(encoding="utf-8"))
            print(len(data))
            return 0
        if args.memory_command == "list":
            if not store_path.exists():
                print("No semantic memory store found.")
                return 0
            data = json.loads(store_path.read_text(encoding="utf-8"))
            if args.json:
                print(json.dumps(data, indent=2))
                return 0
            for key, entry in sorted(data.items()):
                typ = entry.get("type", "?")
                src = entry.get("source", "?")
                tags = ", ".join(entry.get("tags", [])) or "—"
                preview = entry.get("content", "")[:60].replace("\n", " ")
                print(f"{key}")
                print(f"  type={typ}  source={src}  tags={tags}")
                print(f"  {preview}…")
                print()
            return 0
        parser.error("memory requires one of: audit, count, list")
    if args.command == "release-gate":
        if args.release_gate_command == "run":
            from release_gate import render_release_gate, run_release_gate  # noqa: PLC0415

            test_command = shlex.split(args.test_command) if args.test_command else None
            lint_command = shlex.split(args.lint_command) if args.lint_command else None
            result = run_release_gate(
                args.repo, args.target, test_command=test_command, lint_command=lint_command
            )
            if args.json:
                print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            else:
                print(render_release_gate(result))
            return 1 if result.status == "blocked" else 0
        parser.error("release-gate requires one of: run")

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
