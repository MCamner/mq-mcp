"""Small local CLI for mq-mcp install and runtime workflows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
VERSION_FILE = REPO_ROOT / "VERSION"
PYPROJECT_FILE = APP_DIR / "pyproject.toml"
ENV_FILE = APP_DIR / ".env"
ENV_EXAMPLE_FILE = APP_DIR / ".env.example"


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def run_command(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(args, cwd=cwd, env=merged_env, check=False).returncode


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

    serve_parser = sub.add_parser("serve", help="Run the local MCP server.")
    serve_parser.add_argument("--host", help="Override MQ_MCP_HOST for HTTP/SSE transports.")
    serve_parser.add_argument("--port", help="Override MQ_MCP_PORT for HTTP/SSE transports.")

    sub.add_parser("validate", help="Run scripts/validate.sh from the repository root.")
    sub.add_parser("tools", help="List tools exposed through bridge.py.")

    config_parser = sub.add_parser("config", help="Inspect local config paths.")
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_sub.add_parser("path", help="Print the .env path.")
    config_sub.add_parser("example", help="Print the .env.example path.")
    config_sub.add_parser("root", help="Print the repository root path.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(read_version())
        return 0
    if args.command == "doctor":
        return doctor(json_output=args.json)
    if args.command == "serve":
        env: dict[str, str] = {}
        if args.host:
            env["MQ_MCP_HOST"] = args.host
        if args.port:
            env["MQ_MCP_PORT"] = args.port
        return run_command(["uv", "run", "mcp", "run", "server.py"], APP_DIR, env)
    if args.command == "validate":
        return run_command([str(REPO_ROOT / "scripts" / "validate.sh")], REPO_ROOT)
    if args.command == "tools":
        return run_command(["uv", "run", "python", "bridge.py", "--tools"], APP_DIR)
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
