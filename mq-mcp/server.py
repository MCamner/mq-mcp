import json
import random
import re
import requests
import os
import time
from pathlib import Path
from typing import Any
import psutil
import shutil
import subprocess
import pandas as pd
import guitarpro
from PIL import Image
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Initiera servern. mq-agent expects the local HTTP/SSE bridge on :8765.
MCP_HOST = os.getenv("MQ_MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MQ_MCP_PORT", "8765"))
mcp = FastMCP("mq-mcp", host=MCP_HOST, port=MCP_PORT)

REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTRACTS_PATH = REPO_ROOT / "docs" / "tool_contracts.json"
_STARTED_AT = time.time()


def _contract_class_to_safety(value: object) -> str:
    """Convert tool contract classes into caller-facing safety labels."""
    normalized = str(value or "unknown").strip().lower()
    return {
        "a": "read-only",
        "b": "read-only",
        "c": "write-capable",
        "d": "subprocess",
        "read-only": "read-only",
        "write-capable": "write-capable",
        "subprocess": "subprocess",
        "dangerous": "dangerous",
    }.get(normalized, "unknown")


def _load_safety_map() -> dict[str, str]:
    """Build tool_name → safety_class from tool_contracts.json."""
    try:
        data = json.loads(_CONTRACTS_PATH.read_text(encoding="utf-8"))
        return {
            t["name"]: _contract_class_to_safety(t.get("safety_class") or t.get("class"))
            for t in data.get("tools", [])
        }
    except Exception:
        return {}


_SAFETY_MAP: dict[str, str] = _load_safety_map()


def _version() -> str:
    try:
        return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _request_logging_enabled() -> bool:
    return os.getenv("MQ_MCP_REQUEST_LOG", "").lower() in {"1", "true", "yes", "on"}


def _log_observability_request(request: Request, name: str, started: float) -> None:
    if not _request_logging_enabled():
        return
    elapsed_ms = round((time.time() - started) * 1000, 2)
    print(
        f"mq-mcp request path={request.url.path} route={name} elapsed_ms={elapsed_ms}",
        flush=True,
    )


def _redacted_env() -> dict[str, object]:
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
    redacted: dict[str, object] = {}
    for key in keys:
        value = os.getenv(key)
        if value is None:
            redacted[key] = {"set": False}
        elif any(marker in key for marker in secret_markers):
            redacted[key] = {"set": True, "value": "<redacted>"}
        else:
            redacted[key] = {"set": True, "value": value}
    return redacted


def jsonable(value: Any) -> Any:
    """Convert MCP/Pydantic return values into JSON-serializable objects."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


def _enrich_tool(tool_dict: dict[str, Any]) -> dict[str, Any]:
    """Add safety_class to a serialized tool dict from the contracts map."""
    name = str(tool_dict.get("name", ""))
    tool_dict["safety_class"] = _SAFETY_MAP.get(name, "unknown")  # type: ignore[call-overload]
    return tool_dict


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    started = time.time()
    tools = await mcp.list_tools()
    payload = {
        "status": "ok",
        "name": "mq-mcp",
        "version": _version(),
        "host": MCP_HOST,
        "port": MCP_PORT,
        "tool_count": len(tools),
        "uptime_seconds": round(time.time() - _STARTED_AT, 3),
        "elapsed_ms": round((time.time() - started) * 1000, 2),
    }
    _log_observability_request(request, "health", started)
    return JSONResponse(payload)


@mcp.custom_route("/tool-count", methods=["GET"])
async def tool_count(request: Request) -> JSONResponse:
    started = time.time()
    tools = await mcp.list_tools()
    payload = {
        "name": "mq-mcp",
        "version": _version(),
        "tool_count": len(tools),
        "elapsed_ms": round((time.time() - started) * 1000, 2),
    }
    _log_observability_request(request, "tool-count", started)
    return JSONResponse(payload)


@mcp.custom_route("/server-info", methods=["GET"])
async def server_info(request: Request) -> JSONResponse:
    started = time.time()
    tools = await mcp.list_tools()
    classes: dict[str, int] = {}
    for safety_class in _SAFETY_MAP.values():
        classes[safety_class] = classes.get(safety_class, 0) + 1
    payload = {
        "name": "mq-mcp",
        "version": _version(),
        "repo_root": str(REPO_ROOT),
        "host": MCP_HOST,
        "port": MCP_PORT,
        "tool_count": len(tools),
        "safety_classes": classes,
        "request_logging": _request_logging_enabled(),
        "uptime_seconds": round(time.time() - _STARTED_AT, 3),
        "elapsed_ms": round((time.time() - started) * 1000, 2),
    }
    _log_observability_request(request, "server-info", started)
    return JSONResponse(payload)


@mcp.custom_route("/diagnostics", methods=["GET"])
async def diagnostics(request: Request) -> JSONResponse:
    started = time.time()
    tools = await mcp.list_tools()
    payload = {
        "name": "mq-mcp",
        "version": _version(),
        "status": "ok",
        "repo_root": str(REPO_ROOT),
        "tool_count": len(tools),
        "env": _redacted_env(),
        "paths": {
            "contracts": str(_CONTRACTS_PATH),
            "validate_script": str(REPO_ROOT / "scripts" / "validate.sh"),
        },
        "metrics": {
            "uptime_seconds": round(time.time() - _STARTED_AT, 3),
            "elapsed_ms": round((time.time() - started) * 1000, 2),
        },
    }
    _log_observability_request(request, "diagnostics", started)
    return JSONResponse(payload)


@mcp.custom_route("/tool-contracts", methods=["GET"])
async def serve_tool_contracts(request: Request) -> JSONResponse:
    """Serve the machine-readable tool contract schema."""
    try:
        data = json.loads(_CONTRACTS_PATH.read_text(encoding="utf-8"))
        return JSONResponse(data)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@mcp.custom_route("/tools", methods=["GET"])
async def list_http_tools(request: Request) -> JSONResponse:
    tools = await mcp.list_tools()
    enriched = [_enrich_tool(jsonable(t)) for t in tools]
    return JSONResponse({"tools": enriched})


@mcp.custom_route("/tools/{name}", methods=["GET"])
async def describe_http_tool(request: Request) -> JSONResponse:
    name = request.path_params["name"]
    tools = await mcp.list_tools()
    for tool in tools:
        if tool.name == name:
            return JSONResponse(_enrich_tool(jsonable(tool)))
    return JSONResponse({"error": f"Unknown tool: {name}"}, status_code=404)


@mcp.custom_route("/tools/{name}", methods=["POST"])
async def call_http_tool(request: Request) -> JSONResponse:
    name = request.path_params["name"]
    arguments = await request.json()
    result = await mcp.call_tool(name, arguments)
    return JSONResponse(jsonable(result))

def resolve_repo_file(relative_path: str) -> Path:
    """Resolve a path safely inside the repository root."""
    target = (REPO_ROOT / relative_path).resolve()

    try:
        target.relative_to(REPO_ROOT.resolve())
    except ValueError:
        raise ValueError(f"Blocked path outside repo: {relative_path}")

    return target


def known_local_repos() -> dict[str, Path]:
    """Return registered local repos from MQ_MCP_LOCAL_REPOS.

    Configure with comma-separated absolute paths:
      MQ_MCP_LOCAL_REPOS="/Users/mansys/repo-signal,/Users/mansys/mq-hal"

    Name is derived from the directory basename.
    mq-mcp repo root is always included as 'mq-mcp'.
    """
    repos: dict[str, Path] = {"mq-mcp": REPO_ROOT.resolve()}
    raw = os.getenv("MQ_MCP_LOCAL_REPOS", "")
    for item in raw.split(","):
        item = item.strip()
        if item:
            p = Path(item).expanduser().resolve()
            repos[p.name] = p
    return repos


def allowed_external_roots() -> list[Path]:
    """Return explicit external roots allowed for media/app file tools.

    Includes MQ_MCP_ALLOWED_PATHS and all paths from MQ_MCP_LOCAL_REPOS.

    Configure with:
      MQ_MCP_ALLOWED_PATHS="/Users/mansys/Music:/Users/mansys/Pictures"
      MQ_MCP_LOCAL_REPOS="/Users/mansys/repo-signal,/Users/mansys/mq-hal"
    """
    roots: list[Path] = []
    raw = os.getenv("MQ_MCP_ALLOWED_PATHS", "")
    for item in raw.split(":"):
        item = item.strip()
        if item:
            roots.append(Path(item).expanduser().resolve())
    repo_root = REPO_ROOT.resolve()
    for path in known_local_repos().values():
        if path != repo_root and path not in roots:
            roots.append(path)
    return roots


def resolve_allowed_local_file(file_path: str) -> Path:
    """Resolve a local file inside repo or explicitly allowed external roots.

    Accepts absolute paths or repo-relative paths. External paths require
    MQ_MCP_ALLOWED_PATHS to include the parent directory.
    """
    candidate = Path(file_path).expanduser()
    target = candidate.resolve() if candidate.is_absolute() else (REPO_ROOT / candidate).resolve()

    repo_root = REPO_ROOT.resolve()
    allowed_roots = [repo_root, *allowed_external_roots()]

    for root in allowed_roots:
        try:
            target.relative_to(root)
            return target
        except ValueError:
            continue

    allowed = ", ".join(str(r) for r in allowed_roots)
    raise ValueError(f"Blocked path outside allowed roots: {file_path}. Allowed: {allowed}")


# Definiera tillåten bas-katalog: repo-roten
# server.py ligger i ~/mq-mcp/mq-mcp, därför är parent.parent repo-roten.
# --- SYSTEM & FILER ---

@mcp.tool()
def get_system_resources() -> str:
    """CPU, minne och disk-info."""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    gb = 1024**3
    return f"CPU: {cpu}%, Minne: {memory.percent}%, Disk: {disk.free // gb}GB ledigt"

@mcp.tool()
def read_repo_file(relative_path: str) -> str:
    """Läser innehållet i en fil inom repo-katalogen."""
    try:
        target = resolve_repo_file(relative_path)

        if not target.exists():
            return f"File not found: {relative_path}"

        if not target.is_file():
            return f"Not a file: {relative_path}"

        return target.read_text(encoding="utf-8", errors="replace")

    except Exception as exc:
        return str(exc)
@mcp.tool()
def run_mqlaunch() -> str:
    """Öppnar mqlaunch i ett nytt Terminal-fönster. mqlaunch är ett interaktivt TUI och kräver en riktig terminal."""
    script_path = Path(__file__).resolve().parent / "mqlaunch.sh"

    if not script_path.exists():
        return f"Fel: Hittade inte mqlaunch.sh på {script_path}"

    try:
        subprocess.Popen(
            ["osascript", "-e", f'tell application "Terminal" to do script "zsh {script_path}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "mqlaunch öppnat i ett nytt Terminal-fönster."
    except Exception as e:
        return f"Kunde inte öppna mqlaunch: {e}"

# --- MUSIK & APP-KONTROLL ---

@mcp.tool()
def analyze_guitar_pro(relative_path: str) -> str:
    """Analyserar en Guitar Pro-fil (GP3, GP4, GP5)."""
    try:
        safe_path = resolve_allowed_local_file(relative_path)
        song = guitarpro.parse(str(safe_path))
        return f"Titel: {song.title}, Artist: {song.artist}, Tempo: {song.tempo} BPM"
    except Exception as e: return f"Fel: {str(e)}"

@mcp.tool()
def open_in_app(relative_path: str) -> str:
    """Öppnar en fil i dess standardprogram (t.ex. GP8 eller Photoshop)."""
    try:
        safe_path = resolve_allowed_local_file(relative_path)
        subprocess.run(["open", str(safe_path)], check=True)
        return f"Öppnar '{relative_path}'..."
    except Exception as e: return f"Fel: {str(e)}"

# --- CSV & BILD ---

@mcp.tool()
def analyze_csv(relative_path: str) -> str:
    """Analyserar en CSV-fil inom repo-katalogen."""
    try:
        target = resolve_repo_file(relative_path)
        df = pd.read_csv(target)
        return f"Rader: {len(df)}, Kolumner: {list(df.columns)}\n{df.describe().to_string()}"
    except Exception as e:
        return f"Fel: {str(e)}"

@mcp.tool()
def edit_image(relative_path: str, action: str, value: int | None = None) -> str:
    """Redigerar en bild (resize, rotate, grayscale)."""
    try:
        safe_path = resolve_allowed_local_file(relative_path)
        with Image.open(safe_path) as img:
            if action == "rotate": img = img.rotate(value or 90, expand=True)  # type: ignore[assignment]
            elif action == "grayscale": img = img.convert("L")  # type: ignore[assignment]
            img.save(safe_path)
            return f"Bilden har uppdaterats ({action})."
    except Exception as e: return f"Fel: {str(e)}"


# --- REPO INTELLIGENCE TOOLS ---

def run_repo_command(args: list[str], timeout: int = 20) -> str:
    """Run a safe read-only command inside the repository root."""
    try:
        process = subprocess.run(
            args,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = ""
        if process.stdout:
            output += process.stdout
        if process.stderr:
            output += ("\n" if output else "") + process.stderr
        if not output.strip():
            output = f"Command exited with code {process.returncode} and produced no output."
        return output.strip()
    except Exception as exc:
        return f"Command failed: {exc}"


@mcp.tool()
def list_repo_files(max_depth: int = 3) -> str:
    """List files in the repository, excluding common cache/build folders."""
    ignored_dirs = {
        ".git",
        ".venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
    }

    root = REPO_ROOT.resolve()
    results: list[str] = []

    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)

        if any(part in ignored_dirs for part in rel.parts):
            continue

        if len(rel.parts) > max_depth:
            continue

        if path.is_file():
            results.append(str(rel))

    if not results:
        return "No repository files found."

    return "\n".join(results)


@mcp.tool()
def search_repo(query: str, glob: str | None = None) -> str:
    """Search repository text using git grep. Read-only."""
    if not query.strip():
        return "Search query is empty."

    args = ["git", "grep", "-n", "--", query]

    if glob:
        args.extend(["--", glob])

    result = run_repo_command(args)

    if "Command exited with code 1" in result:
        return f"No matches found for: {query}"

    return result


@mcp.tool()
def git_status() -> str:
    """Show current git branch, status, and latest commit. Read-only."""
    status = run_repo_command(["git", "status", "--short", "--branch"])
    latest = run_repo_command(["git", "log", "--oneline", "-5"])

    return f"""Git status:

{status}

Latest commits:

{latest}
"""


@mcp.tool()
def git_diff(relative_path: str | None = None) -> str:
    """Show git diff for the repo or a specific relative path. Read-only."""
    args = ["git", "diff", "--"]

    if relative_path:
        try:
            target = resolve_repo_file(relative_path)
            rel = str(target.relative_to(REPO_ROOT.resolve()))
            args.append(rel)
        except Exception as exc:
            return f"Invalid path: {exc}"

    result = run_repo_command(args)

    if "produced no output" in result:
        return "No diff."

    return result



@mcp.tool()
def update_repo_file(relative_path: str, old_text: str, new_text: str) -> str:
    """Safely update a text file inside the repo by replacing exact text. Does not commit."""
    try:
        target = resolve_repo_file(relative_path)
        root = REPO_ROOT.resolve()
        rel = target.relative_to(root)

        blocked_names = {".env", ".env.local", ".envrc", "uv.lock"}
        blocked_parts = {".git", ".venv", "__pycache__", "node_modules"}
        allowed_suffixes = {
            ".md",
            ".txt",
            ".py",
            ".sh",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
            ".html",
            ".css",
            ".js",
        }

        if any(part in blocked_parts for part in rel.parts):
            return f"Blocked path: {relative_path}"

        if target.name in blocked_names:
            return f"Blocked file: {relative_path}"

        if target.suffix and target.suffix not in allowed_suffixes:
            return f"Blocked file type: {target.suffix}"

        if not target.exists():
            return f"File not found: {relative_path}"

        if not target.is_file():
            return f"Not a file: {relative_path}"

        if not old_text:
            return "old_text must not be empty."

        content = target.read_text(encoding="utf-8", errors="replace")

        count = content.count(old_text)
        if count == 0:
            return "No exact match found. File was not changed."

        if count > 1:
            return f"Refusing to update: old_text matched {count} times. Make old_text more specific."

        updated = content.replace(old_text, new_text, 1)

        if updated == content:
            return "No change produced. File was not changed."

        target.write_text(updated, encoding="utf-8")

        diff = run_repo_command(["git", "diff", "--", str(rel)])

        return f"""Updated {relative_path}

Changed:
- replaced 1 exact text block
- did not commit

Diff:

{diff}
"""

    except Exception as exc:
        return f"update_repo_file failed: {exc}"

@mcp.tool()
def validate_project() -> str:
    """Run the local project validation script if it exists."""
    script = REPO_ROOT / "scripts" / "validate.sh"

    if not script.exists():
        return "Validation script not found: scripts/validate.sh"

    if not script.is_file():
        return "Validation path exists but is not a file: scripts/validate.sh"

    return run_repo_command(["bash", str(script)], timeout=60)


@mcp.tool()
def tool_safety_report() -> str:
    """Return the documented MCP tool safety classification.

    Read-only. No subprocess, no external file access.
    Exposes docs/TOOL_SAFETY.md so MCP clients can inspect tool scope,
    access type, and risk level without touching anything outside the repo.
    """
    safety_doc = REPO_ROOT / "docs" / "TOOL_SAFETY.md"

    if not safety_doc.exists():
        return "Missing docs/TOOL_SAFETY.md. Run scripts/check-mcp-tool-docs.sh."

    return safety_doc.read_text(encoding="utf-8")


@mcp.tool()
def list_local_repos() -> str:
    """List all registered local repositories by name and path. Read-only.

    Includes mq-mcp itself and any repos configured in MQ_MCP_LOCAL_REPOS.
    """
    repos = known_local_repos()
    if not repos:
        return "No local repos registered. Set MQ_MCP_LOCAL_REPOS in .env."
    lines = ["Registered local repos:", ""]
    for name, path in sorted(repos.items()):
        exists = "exists" if path.exists() else "missing"
        lines.append(f"  {name}: {path} ({exists})")
    return "\n".join(lines)


@mcp.tool()
def open_repo_terminal(name: str) -> str:
    """Open a registered local repository in a new Terminal window.

    Looks up the repo by name from MQ_MCP_LOCAL_REPOS (or 'mq-mcp' for this repo).
    Opens a new Terminal window cd'd into that directory via osascript.

    Args:
        name: Repository name as registered in MQ_MCP_LOCAL_REPOS.
    """
    repos = known_local_repos()
    if name not in repos:
        available = ", ".join(sorted(repos.keys()))
        return f"Unknown repo: '{name}'. Available: {available}"

    path = repos[name]
    if not path.exists():
        return f"Repo path does not exist: {path}"

    try:
        subprocess.Popen(
            ["osascript", "-e", f'tell application "Terminal" to do script "cd {path} && clear"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Opened Terminal at {name}: {path}"
    except Exception as exc:
        return f"Could not open Terminal: {exc}"


def _resolve_signal_repo(repo_path: str) -> Path:
    """Resolve a repo path for repo-signal tools.

    Accepts paths within MQ_MCP_ALLOWED_PATHS or REPO_ROOT.
    Raises ValueError on traversal outside allowed roots.
    """
    return resolve_allowed_local_file(repo_path)


def _run_repo_signal(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run repo-signal CLI as a subprocess. Raises FileNotFoundError if not installed."""
    return subprocess.run(
        ["repo-signal", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


@mcp.tool()
def repo_signal_analyze(repo_path: str = ".") -> str:
    """Run repo-signal analyze on a local repository. Read-only.

    Returns a structured report covering project type, languages, entry points,
    top directories, tooling, and git state. Path must be within MQ_MCP_ALLOWED_PATHS
    or the mq-mcp repository root.

    Args:
        repo_path: Absolute or repo-relative path to the repository root. Defaults to mq-mcp repo.
    """
    try:
        target = _resolve_signal_repo(repo_path)
        result = _run_repo_signal(["analyze", str(target)], cwd=target)
        return result.stdout or result.stderr or "repo_signal_analyze returned no output"
    except FileNotFoundError:
        return "repo-signal is not installed or not on PATH"
    except Exception as exc:
        return f"repo_signal_analyze failed: {exc}"


@mcp.tool()
def repo_signal_checklist(repo_path: str = ".") -> str:
    """Run repo-signal publish checklist on a local repository. Read-only.

    Returns an OK/WARN checklist covering README quality, LICENSE, CHANGELOG,
    GitHub Pages, release signals, and documentation completeness. Path must be
    within MQ_MCP_ALLOWED_PATHS or the mq-mcp repository root.

    Args:
        repo_path: Absolute or repo-relative path to the repository root. Defaults to mq-mcp repo.
    """
    try:
        target = _resolve_signal_repo(repo_path)
        result = _run_repo_signal(["publish-checklist", str(target)], cwd=target)
        return result.stdout or result.stderr or "repo_signal_checklist returned no output"
    except FileNotFoundError:
        return "repo-signal is not installed or not on PATH"
    except Exception as exc:
        return f"repo_signal_checklist failed: {exc}"


@mcp.tool()
def repo_signal_inspect(repo_path: str = ".") -> dict:
    """Run repo-signal inspect --json and return structured inspect.v1 data. Read-only.

    Returns machine-readable repository state: public readiness, detected signals,
    core files, possible issues, and recommended next commit. Uses the stable
    inspect.v1 JSON contract. Path must be within MQ_MCP_ALLOWED_PATHS or the
    mq-mcp repository root.

    Args:
        repo_path: Absolute or repo-relative path to the repository root. Defaults to mq-mcp repo.
    """
    import json as _json
    try:
        target = _resolve_signal_repo(repo_path)
        result = _run_repo_signal(["inspect", "--json", str(target)], cwd=target)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "inspect failed", "repo_path": str(target)}
        return _json.loads(result.stdout)
    except FileNotFoundError:
        return {"error": "repo-signal is not installed or not on PATH"}
    except _json.JSONDecodeError as exc:
        return {"error": f"inspect returned invalid JSON: {exc}"}
    except Exception as exc:
        return {"error": f"repo_signal_inspect failed: {exc}"}


@mcp.tool()
def repo_signal_doctor_json(repo_path: str = ".") -> dict:
    """Run repo-signal doctor --json and return structured doctor.v1 data. Read-only.

    Returns machine-readable repo health: scores for repo health, release maturity,
    docs quality, and AI readiness. Uses the stable doctor.v1 JSON contract. Path
    must be within MQ_MCP_ALLOWED_PATHS or the mq-mcp repository root.

    Args:
        repo_path: Absolute or repo-relative path to the repository root. Defaults to mq-mcp repo.
    """
    import json as _json
    try:
        target = _resolve_signal_repo(repo_path)
        result = _run_repo_signal(["doctor", "--json", str(target)], cwd=target)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "doctor --json failed", "repo_path": str(target)}
        return _json.loads(result.stdout)
    except FileNotFoundError:
        return {"error": "repo-signal is not installed or not on PATH"}
    except _json.JSONDecodeError as exc:
        return {"error": f"doctor returned invalid JSON: {exc}"}
    except Exception as exc:
        return {"error": f"repo_signal_doctor_json failed: {exc}"}


@mcp.tool()
def hal_repo_report(mode: str = "audit", repo: str = "mq-mcp") -> str:
    """Run a read-only mq-hal repository report.

    Connects the mq-mcp MCP surface to mq-hal's local repo helpers.

    Supported modes:
    - audit: publish quality and README score through mq-hal/repo-signal
    - brief: compact repository status brief
    - release-brief: release readiness summary
    - repo-status: read-only git repository status
    - repo-status-json: structured JSON repo state via inspect.v1 + doctor.v1
    - ci: GitHub Actions status

    Read-only. Delegates to the local mq-hal CLI via a fixed command allowlist.
    """
    allowed_repo_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    )
    if not repo or any(ch not in allowed_repo_chars for ch in repo):
        return "Unsupported repo name. Use only letters, numbers, dot, dash, and underscore."

    commands: dict[str, list[str]] = {
        "audit":            ["mq-hal", "audit",            "--repo", repo],
        "brief":            ["mq-hal", "brief",            "--repo", repo],
        "release-brief":    ["mq-hal", "release-brief",    "--repo", repo],
        "repo-status":      ["mq-hal", "repo-status",      "--repo", repo],
        "repo-status-json": ["mq-hal", "repo-status-json", "--repo", repo],
        "ci":               ["mq-hal", "ci",               "--repo", repo],
    }

    if mode not in commands:
        return (
            f"Unsupported mode: {mode}\n"
            f"Supported modes: {', '.join(sorted(commands))}"
        )

    try:
        result = subprocess.run(
            commands[mode],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        return "mq-hal not found. Install mq-hal and make sure it is in PATH."
    except subprocess.TimeoutExpired:
        return "mq-hal timed out after 180 seconds."

    output = result.stdout.strip()
    error = result.stderr.strip()

    if result.returncode != 0:
        return (
            f"mq-hal exited with code {result.returncode}.\n\n"
            f"STDOUT:\n{output}\n\nSTDERR:\n{error}"
        )

    return output or "mq-hal completed with no output."


@mcp.tool()
def open_messages(contact: str = "") -> str:
    """Open Messages.app, optionally to a specific contact or phone number.

    Args:
        contact: Name, phone number, or email to open a conversation with. Leave empty to just open Messages.
    """
    try:
        if contact:
            subprocess.Popen(
                ["osascript", "-e",
                 f'tell application "Messages" to activate\n'
                 f'tell application "Messages" to activate'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.Popen(["open", f"sms:{contact}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Opened Messages to: {contact}"
        else:
            subprocess.Popen(["open", "-a", "Messages"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Opened Messages."
    except Exception as exc:
        return f"Could not open Messages: {exc}"


@mcp.tool()
def open_finder(path: str = "") -> str:
    """Open Finder at a given path, or at the home directory if no path is given.

    Args:
        path: Absolute path to open in Finder. Leave empty for home directory.
    """
    try:
        target = Path(path).expanduser().resolve() if path else Path.home()
        if not target.exists():
            return f"Path does not exist: {target}"
        subprocess.Popen(["open", str(target)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened Finder at: {target}"
    except Exception as exc:
        return f"Could not open Finder: {exc}"


@mcp.tool()
def open_url(url: str) -> str:
    """Open a URL in the default browser.

    Args:
        url: The URL to open. Must start with http:// or https://.
    """
    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    try:
        subprocess.Popen(["open", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened URL: {url}"
    except Exception as exc:
        return f"Could not open URL: {exc}"


@mcp.tool()
def show_notification(title: str, message: str, subtitle: str = "") -> str:
    """Send a macOS notification via osascript.

    Args:
        title: Notification title.
        message: Notification body text.
        subtitle: Optional subtitle line.
    """
    try:
        script = f'display notification "{message}" with title "{title}"'
        if subtitle:
            script += f' subtitle "{subtitle}"'
        subprocess.run(["osascript", "-e", script],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Notification sent: {title}"
    except Exception as exc:
        return f"Could not send notification: {exc}"


@mcp.tool()
def get_clipboard() -> str:
    """Return the current contents of the macOS clipboard."""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
        content = result.stdout
        if not content:
            return "(clipboard is empty)"
        return content[:4000]
    except Exception as exc:
        return f"Could not read clipboard: {exc}"


@mcp.tool()
def set_clipboard(text: str) -> str:
    """Copy text to the macOS clipboard.

    Args:
        text: Text to place on the clipboard.
    """
    try:
        subprocess.run(["pbcopy"], input=text, text=True, check=False)
        preview = text[:60] + ("…" if len(text) > 60 else "")
        return f"Copied to clipboard: {preview}"
    except Exception as exc:
        return f"Could not write to clipboard: {exc}"


@mcp.tool()
def open_app(app_name: str) -> str:
    """Launch a macOS application by name.

    Args:
        app_name: Application name as it appears in /Applications, e.g. 'Safari', 'Notes', 'Calendar'.
    """
    if not app_name or "/" in app_name:
        return "Invalid app name."
    try:
        result = subprocess.run(
            ["open", "-a", app_name],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return f"Could not open '{app_name}': {result.stderr.strip()}"
        return f"Opened: {app_name}"
    except Exception as exc:
        return f"Could not open app: {exc}"


@mcp.tool()
def get_wifi_info() -> str:
    """Return the current Wi-Fi network name and signal info."""
    try:
        result = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        # Fallback: networksetup
        result2 = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        return result2.stdout.strip() or "No Wi-Fi info available."
    except Exception as exc:
        return f"Could not get Wi-Fi info: {exc}"


@mcp.tool()
def speak_text(text: str, voice: str = "") -> str:
    """Speak text aloud using macOS text-to-speech.

    Args:
        text: The text to speak.
        voice: Optional macOS voice name, e.g. 'Samantha', 'Alex'. Leave empty for system default.
    """
    if not text:
        return "Nothing to speak."
    try:
        cmd = ["say"]
        if voice:
            cmd += ["-v", voice]
        cmd.append(text[:500])
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Speaking: {text[:60]}{'…' if len(text) > 60 else ''}"
    except Exception as exc:
        return f"Could not speak: {exc}"


@mcp.tool()
def take_screenshot(output_path: str = "") -> str:
    """Take a screenshot and save it to a file.

    Args:
        output_path: Absolute path for the output PNG file. Defaults to ~/Desktop/screenshot.png.
    """
    try:
        if output_path:
            dest = Path(output_path).expanduser().resolve()
        else:
            dest = Path.home() / "Desktop" / "screenshot.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["screencapture", "-x", str(dest)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return f"screencapture failed: {result.stderr.strip()}"
        return f"Screenshot saved: {dest}"
    except Exception as exc:
        return f"Could not take screenshot: {exc}"


@mcp.tool()
def open_chrome(url: str = "") -> str:
    """Open Google Chrome, optionally to a specific URL.

    Args:
        url: URL to navigate to. Leave empty to just open Chrome.
    """
    if url and not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    try:
        cmd = ["open", "-a", "Google Chrome"]
        if url:
            cmd.append(url)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened Chrome{': ' + url if url else '.'}"
    except Exception as exc:
        return f"Could not open Chrome: {exc}"


@mcp.tool()
def open_spotify(uri: str = "") -> str:
    """Open Spotify, optionally to a track, album, playlist, or search.

    Args:
        uri: Spotify URI (spotify:track:…) or search query. Leave empty to just open Spotify.
    """
    try:
        if uri.startswith("spotify:"):
            subprocess.Popen(["open", uri],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Opened Spotify URI: {uri}"
        elif uri:
            from urllib.parse import quote
            search_url = f"spotify:search:{quote(uri)}"
            subprocess.Popen(["open", search_url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Opened Spotify search: {uri}"
        else:
            subprocess.Popen(["open", "-a", "Spotify"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Opened Spotify."
    except Exception as exc:
        return f"Could not open Spotify: {exc}"


@mcp.tool()
def open_terminal(path: str = "") -> str:
    """Open a new Terminal window, optionally cd'd into a given path.

    Args:
        path: Absolute path to open Terminal at. Leave empty for home directory.
    """
    try:
        if path:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return f"Path does not exist: {target}"
            script = f'tell application "Terminal" to do script "cd {target} && clear"'
        else:
            script = 'tell application "Terminal" to do script ""'
        subprocess.Popen(["osascript", "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened Terminal{' at: ' + str(target) if path else '.'}"
    except Exception as exc:
        return f"Could not open Terminal: {exc}"


@mcp.tool()
def open_vscode(path: str = "") -> str:
    """Open Visual Studio Code, optionally at a file or folder.

    Args:
        path: Absolute path to a file or folder to open in VS Code. Leave empty to just open VS Code.
    """
    try:
        code_cmd = shutil.which("code") or "/usr/local/bin/code"
        if path:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return f"Path does not exist: {target}"
            subprocess.Popen([code_cmd, str(target)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Opened VS Code at: {target}"
        else:
            subprocess.Popen([code_cmd],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Opened VS Code."
    except Exception as exc:
        return f"Could not open VS Code: {exc}"


# --- SYSTEM CONTROLS ---

@mcp.tool()
def set_volume(level: int) -> str:
    """Set the macOS system output volume.

    Args:
        level: Volume level 0–100.
    """
    level = max(0, min(100, level))
    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            check=False,
        )
        return f"Volume set to {level}."
    except Exception as exc:
        return f"Could not set volume: {exc}"


@mcp.tool()
def get_battery_status() -> str:
    """Return battery level, charging state, and estimated time remaining."""
    try:
        result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=False)
        return result.stdout.strip() or "No battery info available."
    except Exception as exc:
        return f"Could not get battery status: {exc}"


@mcp.tool()
def toggle_dark_mode() -> str:
    """Toggle macOS between dark mode and light mode."""
    try:
        script = (
            'tell application "System Events" to tell appearance preferences '
            'to set dark mode to not dark mode'
        )
        subprocess.run(["osascript", "-e", script], check=False)
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to tell appearance preferences to return dark mode'],
            capture_output=True, text=True, check=False,
        )
        mode = "Dark" if result.stdout.strip() == "true" else "Light"
        return f"Switched to {mode} mode."
    except Exception as exc:
        return f"Could not toggle dark mode: {exc}"


@mcp.tool()
def list_running_apps() -> str:
    """List all visible macOS applications currently running."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of (processes where background only is false)'],
            capture_output=True, text=True, check=False,
        )
        apps = [a.strip() for a in result.stdout.strip().split(",") if a.strip()]
        if not apps:
            return "No running apps found."
        return "Running apps:\n" + "\n".join(f"- {a}" for a in sorted(apps))
    except Exception as exc:
        return f"Could not list running apps: {exc}"


@mcp.tool()
def lock_screen() -> str:
    """Lock the macOS screen immediately."""
    try:
        subprocess.Popen(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "q" using {command down, control down}'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return "Screen locked."
    except Exception as exc:
        return f"Could not lock screen: {exc}"


# --- PRODUCTIVITY ---

@mcp.tool()
def create_note(title: str, body: str = "") -> str:
    """Create a new note in Notes.app.

    Args:
        title: Note title.
        body: Note body text. Leave empty for a title-only note.
    """
    safe_title = title.replace('"', '\\"')
    safe_body = body.replace('"', '\\"')
    try:
        script = (
            f'tell application "Notes" to make new note '
            f'with properties {{name:"{safe_title}", body:"{safe_body}"}}'
        )
        subprocess.run(["osascript", "-e", script], check=False)
        return f"Note created: {title}"
    except Exception as exc:
        return f"Could not create note: {exc}"


@mcp.tool()
def get_todays_events() -> str:
    """Return today's events from Calendar.app."""
    try:
        script = """
tell application "Calendar"
    set theDate to current date
    set startOfDay to theDate - (time of theDate)
    set endOfDay to startOfDay + 86399
    set result to {}
    repeat with cal in calendars
        set evts to (every event of cal whose start date >= startOfDay and start date <= endOfDay)
        repeat with e in evts
            set end of result to (summary of e) & " @ " & (time string of (start date of e))
        end repeat
    end repeat
    if result is {} then return "No events today."
    return result as text
end tell
"""
        out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        return out.stdout.strip() or out.stderr.strip() or "No events today."
    except Exception as exc:
        return f"Could not get calendar events: {exc}"


@mcp.tool()
def set_reminder(text: str, minutes: int = 30) -> str:
    """Create a reminder in Reminders.app.

    Args:
        text: Reminder text.
        minutes: Minutes from now when the reminder fires. Default 30.
    """
    safe_text = text.replace('"', '\\"')
    try:
        script = f"""
tell application "Reminders"
    set dueDate to (current date) + ({minutes} * 60)
    make new reminder with properties {{name:"{safe_text}", due date:dueDate, remind me date:dueDate}}
end tell
"""
        subprocess.run(["osascript", "-e", script], check=False)
        return f"Reminder set: \"{text}\" in {minutes} minute(s)."
    except Exception as exc:
        return f"Could not set reminder: {exc}"


# --- FILES ---

@mcp.tool()
def find_large_files(path: str = ".", min_mb: int = 50) -> str:
    """Find files larger than a given size in a directory.

    Args:
        path: Directory to search. Defaults to current directory.
        min_mb: Minimum file size in megabytes. Default 50.
    """
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"Path does not exist: {target}"
        result = subprocess.run(
            ["find", str(target), "-type", "f", "-size", f"+{min_mb}M",
             "-not", "-path", "*/.git/*"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if not lines:
            return f"No files larger than {min_mb} MB found in {target}."
        return f"Files > {min_mb} MB in {target}:\n" + "\n".join(f"- {l}" for l in lines[:40])
    except Exception as exc:
        return f"Could not search for large files: {exc}"


@mcp.tool()
def find_recent_files(path: str = ".", days: int = 7) -> str:
    """Find files modified within the last N days.

    Args:
        path: Directory to search. Defaults to current directory.
        days: How many days back to look. Default 7.
    """
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"Path does not exist: {target}"
        result = subprocess.run(
            ["find", str(target), "-type", "f", f"-mtime", f"-{days}",
             "-not", "-path", "*/.git/*"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if not lines:
            return f"No files modified in the last {days} day(s) in {target}."
        return f"Files modified last {days} day(s) in {target}:\n" + "\n".join(f"- {l}" for l in lines[:40])
    except Exception as exc:
        return f"Could not search for recent files: {exc}"


# --- DEV ---

@mcp.tool()
def run_tests(repo_name: str) -> str:
    """Run pytest in a registered local repository.

    Args:
        repo_name: Repository name as registered in MQ_MCP_LOCAL_REPOS.
    """
    repos = known_local_repos()
    if repo_name not in repos:
        available = ", ".join(sorted(repos.keys()))
        return f"Unknown repo: '{repo_name}'. Available: {available}"
    path = repos[repo_name]
    if not path.exists():
        return f"Repo path does not exist: {path}"
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "-q", "--tb=short"],
            cwd=str(path), capture_output=True, text=True, check=False, timeout=120,
        )
        out = (result.stdout + result.stderr).strip()
        return out[:4000] or "No output from pytest."
    except subprocess.TimeoutExpired:
        return "pytest timed out after 120 seconds."
    except Exception as exc:
        return f"Could not run tests: {exc}"


@mcp.tool()
def check_port(port: int) -> str:
    """Check whether a TCP port is in use on localhost.

    Args:
        port: Port number to check (1–65535).
    """
    if not (1 <= port <= 65535):
        return "Port must be between 1 and 65535."
    try:
        result = subprocess.run(
            ["lsof", "-i", f"TCP:{port}", "-sTCP:LISTEN", "-n", "-P"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) <= 1:
            return f"Port {port} is free."
        return f"Port {port} is in use:\n" + "\n".join(lines[1:])
    except Exception as exc:
        return f"Could not check port: {exc}"


# --- FUN ---

@mcp.tool()
def set_wallpaper(path: str) -> str:
    """Set the macOS desktop wallpaper.

    Args:
        path: Absolute path to an image file (jpg, png, etc.).
    """
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"File does not exist: {target}"
        script = f'tell application "System Events" to set desktop picture to POSIX file "{target}"'
        subprocess.run(["osascript", "-e", script], check=False)
        return f"Wallpaper set to: {target}"
    except Exception as exc:
        return f"Could not set wallpaper: {exc}"


@mcp.tool()
def get_public_ip() -> str:
    """Return the current public IP address."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5", "https://api.ipify.org"],
            capture_output=True, text=True, check=False, timeout=8,
        )
        ip = result.stdout.strip()
        return f"Public IP: {ip}" if ip else "Could not determine public IP."
    except Exception as exc:
        return f"Could not get public IP: {exc}"


# --- APP DIRECTORY ---

@mcp.tool()
def list_openable_apps() -> str:
    """List all applications Bridget can open or control directly."""
    return """Apps Bridget can open:

Dedicated tools (with extra options):
- Messages          open_messages(contact="")      — open to a contact or number
- Finder            open_finder(path="")           — open at a specific path
- Google Chrome     open_chrome(url="")            — open to a URL
- Spotify           open_spotify(uri="")           — open, search, or Spotify URI
- Terminal          open_terminal(path="")         — new window, optionally cd'd
- Visual Studio Code  open_vscode(path="")         — open file or folder

Any app by name:
- open_app(app_name)  — opens any app in /Applications, e.g.:
    Safari, Notes, Calendar, Reminders, Mail, Maps, Music,
    Photos, Preview, TextEdit, FaceTime, Contacts, Xcode,
    Slack, Discord, Figma, Notion, Obsidian, Ghostty, iTerm,
    1Password, CleanMyMac, Keynote, Pages, Numbers, …

Type: open_app("AppName") to launch anything not listed above."""


# --- REVIEW ENGINE ---

def _load_review_contract(mode: str) -> str:
    """Load a review contract markdown by mode name. Falls back to comment-review."""
    contracts_dir = REPO_ROOT / "reviews" / "contracts"
    candidate = contracts_dir / f"{mode}-review.md"
    fallback = contracts_dir / "comment-review.md"

    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")
    return ""


def _load_architecture_role(relative_path: str) -> str:
    """Return the architecture role for a file from the cached context map, if available."""
    ctx_path = REPO_ROOT / "review_engine" / "context" / "architecture_map.json"
    if not ctx_path.exists():
        return ""
    try:
        data = json.loads(ctx_path.read_text(encoding="utf-8"))
        return data.get(relative_path, "")
    except Exception:
        return ""


def _build_rich_cross_file_context(relative_path: str, mem=None, max_related: int = 4) -> str:
    """Build rich cross-file context from callgraph, arch map, and review memory.

    For each file that imports or is imported by relative_path, includes:
    architecture role, top public symbols, and last review summary.
    """
    cg_path = REPO_ROOT / "review_engine" / "context" / "callgraph.json"
    if not cg_path.exists():
        return ""
    try:
        cg = json.loads(cg_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    rel = relative_path.replace("\\", "/")
    deps = cg.get("imports", {}).get(rel, [])
    dependents = cg.get("importers", {}).get(rel, [])
    is_hub = rel in cg.get("hub_files", [])
    symbols_map = cg.get("symbols", {})

    if not deps and not dependents:
        return ""

    arch_map: dict = {}
    arch_map_path = REPO_ROOT / "review_engine" / "context" / "architecture_map.json"
    if arch_map_path.exists():
        try:
            arch_map = json.loads(arch_map_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    lines = ["## Cross-file context"]
    if is_hub:
        n = len(cg.get("importers", {}).get(rel, []))
        lines.append(f"Hub file — imported by {n} files.")

    # Interleave deps and dependents up to max_related
    half = max_related // 2
    related = (
        [(f, "imports") for f in deps[: half + 1]]
        + [(f, "imported by") for f in dependents[: half + 1]]
    )[:max_related]

    for file_rel, relation in related:
        fname = Path(file_rel).name
        lines.append(f"\n**{fname}** ({relation} this file)")

        role = arch_map.get(file_rel, "")
        if role and role != "unknown":
            lines.append(f"Role: {role}")

        syms = symbols_map.get(file_rel, [])[:5]
        if syms:
            lines.append(f"Symbols: {', '.join(syms)}")

        if mem is not None:
            try:
                last = mem.get_last(file_rel)
                if last:
                    age_str = f"{last.age_days():.0f}d ago" if last.age_days() >= 1 else "today"
                    dist = ", ".join(
                        f"{k}:{v}" for k, v in sorted(last.severity_counts.items()) if v
                    )
                    lines.append(
                        f"Last review: {last.finding_count} findings ({dist}) — {age_str}"
                    )
            except Exception:
                pass

    return "\n".join(lines)


# ── type annotation pre-scan ─────────────────────────────────────────────────

def _detect_type_issues(file_path: str, content: str) -> str:
    """AST-based pre-scan for missing type annotations in Python files.

    Checks public functions and methods for missing return type annotations
    and unannotated parameters (excluding `self` and `cls`).
    Returns [WARNING] findings text, or empty string if clean.
    No API call — stdlib ast only.
    """
    import ast as _ast

    if not file_path.endswith(".py"):
        return ""

    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return ""

    lines = content.splitlines()
    hits: list[str] = []

    for node in _ast.walk(tree):
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        # Skip private functions — type annotation style only matters for public API
        if node.name.startswith("_"):
            continue

        # Missing return annotation
        if node.returns is None:
            hits.append(
                f"[WARNING] {file_path}:{node.lineno}\n"
                f"{node.name}() has no return type annotation."
            )

        # Unannotated parameters (skip self/cls)
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation is None:
                hits.append(
                    f"[WARNING] {file_path}:{node.lineno}\n"
                    f"{node.name}(): parameter '{arg.arg}' has no type annotation."
                )

    if not hits:
        return ""
    return "## Pre-scan: type annotation gaps (AST)\n\n" + "\n\n".join(hits)


# ── security pre-scan ─────────────────────────────────────────────────────────

_SECURITY_PATTERNS: list[tuple[str, str, str]] = [
    # (regex_pattern, severity, description)
    (r"os\.system\s*\(",              "RISK",    "os.system() — shell injection if argument contains user input"),
    (r"subprocess\.[a-z_]+\(.*shell\s*=\s*True", "RISK", "subprocess with shell=True — shell metacharacters in any arg become injection"),
    (r"\beval\s*\(",                  "RISK",    "eval() — arbitrary code execution if argument is user-controlled"),
    (r"\bexec\s*\(",                  "RISK",    "exec() — arbitrary code execution if argument is user-controlled"),
    (r"os\.popen\s*\(",               "RISK",    "os.popen() — shell execution, same risk as os.system"),
    (r"pickle\.loads?\s*\(",          "WARNING", "pickle.load(s)() — arbitrary code execution on untrusted data"),
    (r"yaml\.load\s*\([^)]*(?<!SafeLoader)\)", "WARNING", "yaml.load() without SafeLoader — unsafe deserialization"),
    (r'api_key\s*=\s*["\'][^"\']{8,}', "WARNING", "Possible hardcoded API key literal"),
    (r'password\s*=\s*["\'][^"\']{4,}', "WARNING", "Possible hardcoded password literal"),
    (r'token\s*=\s*["\'][^"\']{8,}',  "WARNING", "Possible hardcoded token literal"),
    (r"__import__\s*\(",              "WARNING", "Dynamic import — code execution if module name is user-controlled"),
]

_SHELL_PATTERNS: list[tuple[str, str, str]] = [
    (r'\beval\s+"?\$',                "RISK",    "eval with variable expansion — arbitrary code execution"),
    (r"curl\s+.*\|\s*bash",           "CRITICAL", "curl | bash — remote code execution"),
    (r"rm\s+-rf\s+\$",               "WARNING", "rm -rf with unquoted variable — potential destructive expansion"),
]


def _blank_python_strings(content: str) -> list[str]:
    """Return lines with Python string literal CONTENT blanked out.

    Uses tokenize for accuracy — correctly handles raw strings, multi-line
    strings, and adjacent strings without false cross-boundary matches.
    String delimiters are kept so the line structure is preserved; only the
    content (which causes false-positive pattern matches) is replaced with spaces.
    Falls back to the original lines if tokenization fails.
    """
    import io
    import tokenize as _tok

    try:
        lines = content.splitlines(keepends=True)
        # Build a mutable list of char lists for surgical blanking
        chars = [list(line) for line in lines]
        tokens = list(_tok.generate_tokens(io.StringIO(content).readline))
        for tok_type, tok_str, (srow, scol), (erow, ecol), _ in tokens:
            if tok_type != _tok.STRING:
                continue
            # Only blank strings whose content contains spaces — keeps short
            # strings (API keys, variable names) intact for matching.
            if " " not in tok_str:
                continue
            # Blank out the string content character by character, row by row.
            # We zero out everything INSIDE the quotes (not the delimiters).
            for row in range(srow, erow + 1):
                row_idx = row - 1
                if row_idx >= len(chars):
                    continue
                start_col = scol + _quote_prefix_len(tok_str) if row == srow else 0
                end_col = ecol if row == erow else len(chars[row_idx])
                for col in range(start_col, end_col):
                    if col < len(chars[row_idx]):
                        chars[row_idx][col] = " "
        return ["".join(line) for line in chars]
    except Exception:
        return content.splitlines()


def _quote_prefix_len(tok_str: str) -> int:
    """Return the length of the quote prefix (r\", b\", f\", \"\"\", etc.)."""
    i = 0
    while i < len(tok_str) and tok_str[i].lower() in "rRbBfFuU":
        i += 1
    # Count quote chars (''' or \"\"\" or ' or ")
    q = tok_str[i]
    if tok_str[i:i+3] in ('"""', "'''"):
        return i + 3
    return i + 1


def _detect_security_patterns(file_path: str, content: str) -> str:
    """Grep-based pre-scan for known dangerous patterns. Returns [SEVERITY] findings text.

    For Python files, string literal content (with spaces) is blanked out before
    matching using the tokenizer — prevents false positives from pattern
    definitions and human-readable descriptions that mention the patterns they
    document, while keeping short string values (API keys, tokens) intact for
    detection. Shell files are scanned as-is.
    """
    suffix = Path(file_path).suffix.lower()
    is_shell = suffix in {".sh", ".bash", ".zsh"} or content.startswith("#!/")
    patterns = _SHELL_PATTERNS if is_shell else _SECURITY_PATTERNS

    # For Python files, pre-process to blank description strings
    if not is_shell and suffix == ".py":
        scan_lines = _blank_python_strings(content)
    else:
        scan_lines = content.splitlines()

    hits: list[str] = []
    for lineno, line in enumerate(scan_lines, start=1):
        for pattern, severity, description in patterns:
            if re.search(pattern, line):
                hits.append(f"[{severity}] {file_path}:{lineno}\n{description}")
                break  # one hit per line max

    if not hits:
        return ""
    return "## Pre-scan findings (grep-based, no API)\n\n" + "\n\n".join(hits)


# ── review_file ───────────────────────────────────────────────────────────────

@mcp.tool()
def review_file(relative_path: str, mode: str = "comment", deep: bool = False) -> str:
    """Run an AI review on a repo file using the configured review contract.

    Uses the OpenAI API (OPENAI_API_KEY must be set). The review contract
    for the given mode controls output format and severity labels.

    Args:
        relative_path: Repo-relative path to the file to review.
        mode: Review mode. Must match a contract in reviews/contracts/.
              Supported: 'comment', 'architecture', 'security', 'risk'. Defaults to 'comment'.
              For security and risk modes with grep pre-scan, prefer risk_review_file.
        deep: If True, runs a two-pass review: Pass 1 produces a structural
              analysis of the file; Pass 2 uses that analysis to ground the
              contract-driven review. Higher quality, ~2x API calls. Defaults to False.
    """
    import openai as _openai

    try:
        target = resolve_repo_file(relative_path)
    except ValueError as exc:
        return f"review_file blocked: {exc}"

    if not target.exists() or not target.is_file():
        return f"File not found: {relative_path}"

    if target.stat().st_size > 200_000:
        return f"File too large to review (> 200 KB): {relative_path}"

    try:
        file_content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Could not read file: {exc}"

    contract = _load_review_contract(mode)
    if not contract:
        return f"No review contract found for mode '{mode}'. Add reviews/contracts/{mode}-review.md."

    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    arch_role = _load_architecture_role(relative_path)

    # Load skill via router
    try:
        from review_engine.review_router import route_file as _route_file
        skill_name, skill_content = _route_file(relative_path)
    except Exception:
        skill_name, skill_content = "none", ""

    # Load past review context from memory
    past_context = ""
    _mem = None
    try:
        from review_engine.review_memory import ReviewMemory as _ReviewMemory
        _mem = _ReviewMemory()
        past_context = _mem.format_past_context(relative_path)
    except Exception:
        pass

    # Build rich cross-file context: arch role, symbols, last review for related files
    cross_file_ctx = ""
    try:
        cross_file_ctx = _build_rich_cross_file_context(relative_path, mem=_mem)
    except Exception:
        pass

    # Load relevant architecture decisions for this file
    arch_decisions_ctx = ""
    try:
        from review_engine.architecture_memory import ArchitectureMemory as _ArchMem
        arch_decisions_ctx = _ArchMem().format_context_block(relative_path, max_items=3)
    except Exception:
        pass

    semantic_ctx = ""
    try:
        from semantic_memory.semantic_memory import SemanticMemory as _SemMem
        semantic_ctx = _SemMem().format_context_block(relative_path, max_results=2)
    except Exception:
        pass

    # Context selection: cap injected context to budget.
    # Priority: semantic memory (0) > arch decisions (1) > past findings (2) > cross-file (3).
    # arch_role is always a single line — not subject to budget.
    try:
        from review_engine.context_selector import ContextSelector as _ContextSelector
        _cs = _ContextSelector()
        _cs.add("semantic_ctx", semantic_ctx, priority=0)
        _cs.add("arch_decisions_ctx", arch_decisions_ctx, priority=1)
        _cs.add("past_context", past_context, priority=2)
        _cs.add("cross_file_ctx", cross_file_ctx, priority=3)
        _selected = _cs.selected()
        semantic_ctx = _selected.get("semantic_ctx", "")
        arch_decisions_ctx = _selected.get("arch_decisions_ctx", "")
        past_context = _selected.get("past_context", "")
        cross_file_ctx = _selected.get("cross_file_ctx", "")
    except Exception:
        pass

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return "review_file requires OPENAI_API_KEY to be set."

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    try:
        client = _openai.OpenAI(api_key=api_key)

        if deep:
            try:
                from review_engine.multi_pass_reviewer import MultiPassReviewer as _MultiPassReviewer
                reviewer = _MultiPassReviewer(client, model)
                # Prepend ADR context to cross_file_ctx for deep mode
                deep_cross_ctx = (
                    f"{arch_decisions_ctx}\n\n{cross_file_ctx}"
                    if arch_decisions_ctx and cross_file_ctx
                    else arch_decisions_ctx or cross_file_ctx
                )
                result = reviewer.run(
                    file_path=relative_path,
                    file_content=file_content,
                    contract=contract,
                    arch_role=arch_role,
                    skill_content=skill_content,
                    skill_name=skill_name,
                    past_context=past_context,
                    cross_file_ctx=deep_cross_ctx,
                )
                # result.output is already formatted and deduplicated
                output = result.output
                findings = result.findings
            except Exception as exc:
                return f"review_file failed (deep mode): {exc}"

            if not output:
                return "No review output."

            # Persist to review memory
            try:
                if _mem is not None:
                    from review_engine.severity_engine import severity_counts
                    scounts = severity_counts(findings) if findings else {}
                    _mem.save(
                        file_path=relative_path,
                        mode=mode,
                        findings_text=output,
                        finding_count=len(findings),
                        severity_counts=scounts,
                        model=model,
                        skill=skill_name,
                    )
            except Exception:
                pass

            return output

        else:
            role_context = f"\nArchitecture role: {arch_role}" if arch_role else ""
            skill_section = f"\n\n## Skill: {skill_name}\n\n{skill_content}" if skill_content else ""
            adr_section = f"\n\n{arch_decisions_ctx}" if arch_decisions_ctx else ""
            past_section = f"\n\n## Previous review context\n\n{past_context}" if past_context else ""
            cross_section = f"\n\n{cross_file_ctx}" if cross_file_ctx else ""
            semantic_section = f"\n\n{semantic_ctx}" if semantic_ctx else ""

            # Type annotation pre-scan for comment mode — prevents false positives
            # from the model about annotations that are already present.
            type_prescan = ""
            if mode == "comment":
                _type_hits = _detect_type_issues(relative_path, file_content)
                type_prescan = f"\n\n{_type_hits}" if _type_hits else ""

            system = (
                "You are a code review engine operating under a strict review contract.\n"
                "Follow the contract exactly. Do not deviate from the output format.\n"
                "Do not modify code. Output only structured review findings.\n\n"
                f"{contract}{skill_section}"
            )
            user = (
                f"Review this file under the contract above.\n\n"
                f"File: {relative_path}{role_context}{type_prescan}{semantic_section}{adr_section}{cross_section}{past_section}\n\n"
                f"```\n{file_content}\n```"
            )

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=2048,
            )
            raw = response.choices[0].message.content or ""

            if not raw:
                return "No review output."

            # Parse through severity engine for structured output
            output = raw
            findings = []
            try:
                from review_engine.severity_engine import (
                    parse_findings,
                    format_summary,
                    severity_counts,
                )
                findings = parse_findings(raw)
                if findings:
                    output = format_summary(findings, relative_path)
            except Exception:
                pass

            # Persist to review memory
            try:
                if _mem is not None:
                    scounts = severity_counts(findings) if findings else {}
                    _mem.save(
                        file_path=relative_path,
                        mode=mode,
                        findings_text=output,
                        finding_count=len(findings),
                        severity_counts=scounts,
                        model=model,
                        skill=skill_name,
                    )
            except Exception:
                pass

            return output
    except Exception as exc:
        return f"review_file failed (API call): {exc}"


@mcp.tool()
def build_repo_context() -> str:
    """Rebuild the repo context artifacts used by the review engine.

    Generates:
      review_engine/context/architecture_map.json  — role of each file
      review_engine/context/file_summary_index.json — symbols and docstrings
      review_engine/context/callgraph.json          — import graph, hub files

    Read-only analysis. Does not modify repo files.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    ctx_script = REPO_ROOT / "review_engine" / "repo_context_builder.py"
    if not ctx_script.exists():
        return "repo_context_builder.py not found in review_engine/."

    result = subprocess.run(
        [_sys.executable, str(ctx_script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    out = (result.stdout + result.stderr).strip()

    # Also build callgraph
    cg_out = ""
    flat_arch_map: dict = {}
    try:
        from review_engine.callgraph_builder import CallgraphBuilder as _CGB
        builder = _CGB(repo_root=REPO_ROOT)
        cg_result = builder.build()
        cg_out = "\n" + builder.format_summary(cg_result)
    except Exception as exc:
        cg_out = f"\ncallgraph_builder failed: {exc}"

    # Load flat arch map built by repo_context_builder for enrichment
    try:
        _flat_path = REPO_ROOT / "review_engine" / "context" / "architecture_map.json"
        if _flat_path.exists():
            flat_arch_map = json.loads(_flat_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Write generated artifacts: rich architecture_map.v1 and ownership_map.v1
    gen_out = ""
    try:
        from review_engine.generated_artifacts import (
            build_rich_architecture_map as _build_arch,
            build_ownership_map as _build_own,
        )
        _arch = _build_arch(repo_root=REPO_ROOT, flat_arch_map=flat_arch_map)
        _own = _build_own(repo_root=REPO_ROOT)
        gen_out = (
            f"\ngenerated/architecture/architecture_map.json  "
            f"[{_arch['schema']}  {_arch['file_count']} files]"
            f"\ngenerated/architecture/ownership_map.json     "
            f"[{_own['schema']}  {_own['file_count']} files]"
        )
    except Exception as exc:
        gen_out = f"\ngenerated_artifacts failed: {exc}"

    return (out or "build_repo_context completed with no output.") + cg_out + gen_out


@mcp.tool()
def list_review_contracts() -> str:
    """List available review contracts and their modes.

    Read-only. Shows contracts from reviews/contracts/.
    """
    contracts_dir = REPO_ROOT / "reviews" / "contracts"
    if not contracts_dir.exists():
        return "No reviews/contracts/ directory found."

    files = sorted(contracts_dir.glob("*.md"))
    if not files:
        return "No review contracts found in reviews/contracts/."

    lines = ["Available review contracts:", ""]
    for f in files:
        mode = f.stem.replace("-review", "")
        lines.append(f"  mode={mode!r:20s}  contract={f.name}")
    lines.append("")
    lines.append("Usage: review_file(relative_path='...', mode='comment')")
    lines.append("")
    lines.append("Risk-analysis tools (add grep pre-scan before AI review):")
    lines.append("  risk_review_file(relative_path, mode='security'|'risk'|'architecture')")
    lines.append("  risk_review_diff(mode='security'|'risk'|'architecture')")
    return "\n".join(lines)


@mcp.tool()
def list_review_skills() -> str:
    """List available review skills, their trigger paths, and extensions.

    Shows two routing tiers:
    1. Path-prefix routes — directory prefix triggers a domain-specific skill
       regardless of file type (e.g. review_engine/ → review-engine skill).
    2. Extension routes — file extension triggers a generic skill
       (e.g. .py → python-comment-review skill).

    Security and risk modes always inject the security-review skill
    regardless of file type or path.

    Read-only. Class A.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    try:
        from review_engine.review_router import (
            _PREFIX_ROUTES,
            _ROUTES,
            _SECURITY_SKILL_FILE,
            SKILLS_DIR,
        )
    except Exception as exc:
        return f"list_review_skills failed: could not load review_router: {exc}"

    lines = ["Available review skills:", ""]

    lines.append("Path-prefix routes (checked first — first match wins):")
    for prefix, skill_file in _PREFIX_ROUTES:
        exists = (SKILLS_DIR / skill_file).exists()
        status = "✓" if exists else "MISSING"
        lines.append(f"  {prefix:<35} → {skill_file}  [{status}]")

    lines.append("")
    lines.append("Extension routes (checked after prefix — first match wins):")
    for path_pattern, extensions, skill_file in _ROUTES:
        exists = (SKILLS_DIR / skill_file).exists()
        status = "✓" if exists else "MISSING"
        ext_str = ", ".join(sorted(extensions))
        pat_str = f"  path contains {path_pattern!r}" if path_pattern else ""
        lines.append(f"  {ext_str:<20} {pat_str:<30} → {skill_file}  [{status}]")

    lines.append("")
    lines.append("Security/risk mode override (always injected for security and risk modes):")
    exists = (SKILLS_DIR / _SECURITY_SKILL_FILE).exists()
    lines.append(f"  {_SECURITY_SKILL_FILE}  [{'✓' if exists else 'MISSING'}]")

    return "\n".join(lines)


@mcp.tool()
def list_review_history() -> str:
    """List all files that have review history and their last review summary.

    Read-only. Shows data from review_engine/memory/review_history.json.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from review_engine.review_memory import ReviewMemory as _ReviewMemory
        mem = _ReviewMemory()
        return mem.summary()
    except Exception as exc:
        return f"list_review_history failed: {exc}"


@mcp.tool()
def get_last_review(relative_path: str) -> str:
    """Return the most recent review findings for a repo file.

    Read-only. Fetches from local review memory (review_engine/memory/).
    Returns a summary with severity distribution and full findings text.

    Args:
        relative_path: Repo-relative path to look up in review history.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from review_engine.review_memory import ReviewMemory as _ReviewMemory
        mem = _ReviewMemory()
        entry = mem.get_last(relative_path)
        if entry is None:
            return f"No review history for: {relative_path}"
        dist = "  ".join(f"{k}={v}" for k, v in sorted(entry.severity_counts.items()) if v > 0)
        header = (
            f"Last review: {relative_path}\n"
            f"  mode={entry.mode}  model={entry.model}  skill={entry.skill}\n"
            f"  date={entry.timestamp_iso}  findings={entry.finding_count}  [{dist}]\n"
        )
        return header + "\n" + entry.findings_text
    except Exception as exc:
        return f"get_last_review failed: {exc}"


@mcp.tool()
def detect_architecture_drift() -> str:
    """Detect drift between declared documentation and actual runtime state.

    Checks tool counts (server.py vs README, TOOL_SAFETY.md, tool_contracts.json),
    contract coverage, safety doc coverage, and architecture map freshness.

    Read-only. Requires no API key.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from review_engine.drift_detector import DriftDetector as _DriftDetector
        detector = _DriftDetector()
        findings = detector.detect()
        return detector.format_report(findings)
    except Exception as exc:
        return f"detect_architecture_drift failed: {exc}"


@mcp.tool()
def review_runtime_contract() -> str:
    """Review docs/RUNTIME_CONTRACT.md against actual runtime state.

    Runs two passes:

    1. Structural checks (deterministic, no API key required) — verifies that
       the contract's declared guarantees are present in the implementation:
       - Both path resolvers (resolve_repo_file, resolve_allowed_local_file)
         exist in server.py
       - No auto-commit guarantee: git commit/push absent from server.py
       - No secret leakage guarantee: _redacted_env present in server.py
       - RUNTIME_CONTRACT.md itself exists on disk

    2. AI architecture pass (requires OPENAI_API_KEY) — injects current runtime
       state (tool count, safety class breakdown, resolver names) as context and
       runs the architecture review contract against RUNTIME_CONTRACT.md, asking
       the model to identify claims that diverge from the actual implementation.

    Returns structural findings always, AI findings appended if key is available.
    Read-only. Class A.
    """
    import ast as _ast
    import re as _re
    import sys as _sys

    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    contract_path = REPO_ROOT / "docs" / "RUNTIME_CONTRACT.md"
    server_path = REPO_ROOT / "mq-mcp" / "server.py"
    safety_path = REPO_ROOT / "docs" / "TOOL_SAFETY.md"

    findings: list[str] = []

    # — Structural checks —

    # 1. Contract file exists
    if not contract_path.exists():
        return (
            "review_runtime_contract blocked: docs/RUNTIME_CONTRACT.md does not exist.\n"
            "Create the file first."
        )

    try:
        server_text = server_path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"review_runtime_contract failed: could not read server.py: {exc}"

    # 2. Path resolvers present
    for resolver in ("resolve_repo_file", "resolve_allowed_local_file"):
        if resolver not in server_text:
            findings.append(
                f"[RISK] server.py:{resolver}\n"
                f"RUNTIME_CONTRACT.md declares '{resolver}' as a path boundary enforcer "
                f"but the function is not present in server.py."
            )

    # 3. No auto-commit guarantee: no subprocess execution of git commit/push.
    # Strip comment lines before searching to avoid matching example text in comments.
    code_only = "\n".join(
        ln for ln in server_text.splitlines() if not ln.lstrip().startswith("#")
    )
    for subcommand in ("commit", "push"):
        if _re.search(
            r'subprocess\.[a-z_]+\s*\([^)]*["\']git["\'][^)]*["\']' + subcommand + r'["\']',
            code_only,
        ) or _re.search(
            r'os\.system\s*\([^)]*git\s+' + subcommand,
            code_only,
        ):
            findings.append(
                f"[RISK] server.py\n"
                f"RUNTIME_CONTRACT.md guarantees no auto-commit but "
                f"a subprocess call to 'git {subcommand}' was found in server.py."
            )

    # 4. No secret leakage: _redacted_env must exist
    if "_redacted_env" not in server_text:
        findings.append(
            "[RISK] server.py:_redacted_env\n"
            "RUNTIME_CONTRACT.md guarantees no secret leakage via _redacted_env "
            "but the function is not present in server.py."
        )

    structural_section = (
        "## Structural checks\n\n"
        + (
            "\n\n".join(findings)
            if findings
            else "All structural guarantees verified: resolvers present, "
                 "no auto-commit, _redacted_env present."
        )
    )

    # — Runtime state summary (used as AI context) —
    try:
        tree = _ast.parse(server_text)
        tool_names: list[str] = []
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    attr = dec.func if isinstance(dec, _ast.Call) else dec
                    if (
                        isinstance(attr, _ast.Attribute)
                        and attr.attr == "tool"
                        and isinstance(attr.value, _ast.Name)
                        and attr.value.id == "mcp"
                    ):
                        tool_names.append(node.name)
        actual_count = len(tool_names)
    except Exception:
        tool_names = []
        actual_count = 0

    try:
        safety_text = safety_path.read_text(encoding="utf-8")
        # Only count rows in the summary table section
        m_section = _re.search(r"^## Summary table", safety_text, _re.MULTILINE)
        summary_section = safety_text[m_section.start():] if m_section else safety_text
        class_counts: dict[str, int] = {}
        for line in summary_section.splitlines():
            # Format: | `tool_name` | A | resolver | ...
            m = _re.match(r"^\|\s*`[a-z_]+`\s*\|\s*([A-D])\s*\|", line)
            if m:
                cls = f"Class {m.group(1)}"
                class_counts[cls] = class_counts.get(cls, 0) + 1
        class_summary = "  ".join(f"{k}: {v}" for k, v in sorted(class_counts.items()))
    except Exception:
        class_summary = "unavailable"

    runtime_state = (
        f"## Current runtime state\n\n"
        f"- Tool count: {actual_count}\n"
        f"- Safety class breakdown: {class_summary}\n"
        f"- Path resolvers present: resolve_repo_file, resolve_allowed_local_file\n"
        f"- Tools (first 20): {', '.join(tool_names[:20])}"
        + (f" … (+{actual_count - 20} more)" if actual_count > 20 else "")
    )

    # — AI architecture pass —
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return (
            f"{structural_section}\n\n"
            f"{runtime_state}\n\n"
            "## AI pass\n\nSkipped — OPENAI_API_KEY not set."
        )

    try:
        import openai as _openai

        contract_text = contract_path.read_text(encoding="utf-8")
        arch_contract_path = REPO_ROOT / "reviews" / "contracts" / "architecture-review.md"
        arch_contract = (
            arch_contract_path.read_text(encoding="utf-8")
            if arch_contract_path.exists()
            else ""
        )

        system = (
            "You are a code review engine verifying a runtime contract document against "
            "its actual implementation.\n\n"
            "Follow the architecture review contract exactly. Output only structured "
            "findings in the format: [SEVERITY] file:location\\nbody\n\n"
            f"{arch_contract}\n\n"
            f"{runtime_state}"
        )
        user = (
            "Review docs/RUNTIME_CONTRACT.md below.\n\n"
            "Identify claims in the contract that:\n"
            "- contradict or are unsupported by the current runtime state above\n"
            "- describe guarantees not verifiable from the implementation\n"
            "- make architectural claims that appear stale or incorrect\n\n"
            "Do NOT flag accurate claims. Do NOT summarize. Output findings only.\n\n"
            f"```\n{contract_text}\n```"
        )

        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        client = _openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2048,
        )
        ai_raw = (response.choices[0].message.content or "").strip()

        from review_engine.severity_engine import parse_findings, format_summary
        ai_findings = parse_findings(ai_raw)
        ai_section = (
            "## AI architecture pass\n\n"
            + (format_summary(ai_findings, "docs/RUNTIME_CONTRACT.md") if ai_findings else ai_raw)
        )

    except Exception as exc:
        ai_section = f"## AI architecture pass\n\nFailed: {exc}"

    return f"{structural_section}\n\n{runtime_state}\n\n{ai_section}"


@mcp.tool()
def validate_orchestration_contract() -> str:
    """Verify that the current tool set satisfies the orchestration contract.

    Runs deterministic checks against docs/ORCHESTRATION_CONTRACT.md,
    profiles/*.json, and docs/tool_contracts.json. No API key required.

    Checks performed:
    1. docs/ORCHESTRATION_CONTRACT.md exists and is reasonably fresh
    2. All recommended_tools in each profile exist as registered tools
    3. Read-only profiles do not include write-capable (Class C/D) tools
    4. All write:true tools in tool_contracts.json are Class C
    5. All Class D tools have subprocess:true in tool_contracts.json
    6. Error return prefix consistency in server.py (uses 'failed:' pattern)
    7. Profile max-class constraints from ORCHESTRATION_CONTRACT.md §6

    Returns [PASS], [FAIL], or [WARN] lines followed by a summary.
    Class A — read-only, no API key required.
    """
    import ast as _ast
    import json as _json
    import re as _re

    contract_path = REPO_ROOT / "docs" / "ORCHESTRATION_CONTRACT.md"
    profiles_dir = REPO_ROOT / "profiles"
    contracts_path = REPO_ROOT / "docs" / "tool_contracts.json"
    server_path = REPO_ROOT / "mq-mcp" / "server.py"

    findings: list[str] = []
    passes: list[str] = []

    # — 1. ORCHESTRATION_CONTRACT.md exists and is fresh —
    if not contract_path.exists():
        findings.append(
            "[FAIL] docs/ORCHESTRATION_CONTRACT.md\n"
            "File does not exist. Create it to define the orchestration boundary."
        )
    else:
        try:
            server_mtime = server_path.stat().st_mtime
            contract_mtime = contract_path.stat().st_mtime
            if contract_mtime < server_mtime:
                # Diff-aware: show tools added to server.py since the contract's last commit
                new_tools_info = ""
                try:
                    import subprocess as _sp
                    # Find the commit that last touched ORCHESTRATION_CONTRACT.md
                    _r = _sp.run(
                        ["git", "log", "--format=%H", "-1", "--",
                         "docs/ORCHESTRATION_CONTRACT.md"],
                        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=5,
                    )
                    _contract_commit = _r.stdout.strip()
                    if _contract_commit:
                        # Get server.py at that commit
                        _r2 = _sp.run(
                            ["git", "show", f"{_contract_commit}:mq-mcp/server.py"],
                            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=5,
                        )
                        if _r2.returncode == 0:
                            _old_tree = _ast.parse(_r2.stdout)
                            _old_tools: set[str] = set()
                            for _n in _ast.walk(_old_tree):
                                if isinstance(_n, _ast.FunctionDef):
                                    for _d in _n.decorator_list:
                                        _attr = _d.func if isinstance(_d, _ast.Call) else _d
                                        if (isinstance(_attr, _ast.Attribute)
                                                and _attr.attr == "tool"):
                                            _old_tools.add(_n.name)
                            _new_tools = sorted(registered_tools - _old_tools)
                            if _new_tools:
                                new_tools_info = (
                                    f" New tools since last contract update: "
                                    f"{', '.join(_new_tools[:5])}"
                                    + (f" (+{len(_new_tools)-5} more)"
                                       if len(_new_tools) > 5 else "")
                                )
                except Exception:
                    pass
                findings.append(
                    "[WARN] docs/ORCHESTRATION_CONTRACT.md\n"
                    f"Contract is older than server.py — it may not reflect the current tool set."
                    f"{new_tools_info}"
                )
            else:
                passes.append("[PASS] ORCHESTRATION_CONTRACT.md is present and fresh")
        except Exception:
            passes.append("[PASS] ORCHESTRATION_CONTRACT.md exists")

    # — Load tool_contracts.json —
    try:
        contracts_data = _json.loads(contracts_path.read_text(encoding="utf-8"))
        all_tools: dict[str, dict] = {t["name"]: t for t in contracts_data.get("tools", [])}
    except Exception as exc:
        return f"validate_orchestration_contract failed: cannot load tool_contracts.json: {exc}"

    # — Collect registered tool names from server.py (AST) —
    try:
        server_text = server_path.read_text(encoding="utf-8")
        tree = _ast.parse(server_text)
        registered_tools: set[str] = set()
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    attr = dec.func if isinstance(dec, _ast.Call) else dec
                    if (
                        isinstance(attr, _ast.Attribute)
                        and attr.attr == "tool"
                        and isinstance(attr.value, _ast.Name)
                        and attr.value.id == "mcp"
                    ):
                        registered_tools.add(node.name)
    except Exception as exc:
        return f"validate_orchestration_contract failed: cannot parse server.py: {exc}"

    # — 2 & 7. Profile validation —
    READONLY_PROFILES = {"read-only", "repo-only", "claude-desktop"}
    MAX_CLASS: dict[str, set[str]] = {
        "read-only": {"A"},
        "repo-only": {"A", "C"},
        "claude-desktop": {"A", "B"},
        "codex": {"A", "B"},
        "openai-bridge": {"A", "B"},
        "mq-agent": {"A", "B"},
        "developer": {"A", "B", "C", "D"},
        "local-macos": {"A", "B", "C", "D"},
    }

    for profile_path in sorted(profiles_dir.glob("*.json")):
        try:
            pdata = _json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception as exc:
            findings.append(
                f"[FAIL] profiles/{profile_path.name}\n"
                f"Cannot parse profile JSON: {exc}"
            )
            continue

        pname = pdata.get("name", profile_path.stem)
        recs: list[str] = pdata.get("recommended_tools", [])
        allowed_classes = MAX_CLASS.get(pname, {"A", "B", "C", "D"})

        # Check 2: all recommended tools are registered
        for tool_name in recs:
            if tool_name not in registered_tools:
                findings.append(
                    f"[FAIL] profiles/{profile_path.name}:{tool_name}\n"
                    f"Tool '{tool_name}' in {pname} recommended_tools is not registered in server.py."
                )

        # Check 3 & 7: read-only profiles must not exceed their max class
        if pname in MAX_CLASS and allowed_classes not in ({"A", "B", "C", "D"},):
            for tool_name in recs:
                tc = all_tools.get(tool_name, {})
                tool_class = tc.get("class", "A")
                if tool_class not in allowed_classes:
                    findings.append(
                        f"[FAIL] profiles/{profile_path.name}:{tool_name}\n"
                        f"Profile '{pname}' is restricted to Class {'/'.join(sorted(allowed_classes))} "
                        f"but includes '{tool_name}' which is Class {tool_class}."
                    )

        if not any(f"profiles/{profile_path.name}" in f for f in findings):
            passes.append(f"[PASS] profiles/{profile_path.name}: all {len(recs)} tools valid")

    # — 4. write:true tools must be Class C —
    write_class_violations = []
    for tool_name, tc in all_tools.items():
        if tc.get("write") and tc.get("class") != "C":
            write_class_violations.append(
                f"  {tool_name}: write=true but class={tc.get('class')}"
            )

    if write_class_violations:
        findings.append(
            "[FAIL] docs/tool_contracts.json\n"
            "write:true tools must be Class C:\n" + "\n".join(write_class_violations)
        )
    else:
        passes.append("[PASS] All write:true tools are Class C")

    # — 5. Class D tools must have subprocess:true —
    class_d_no_sub = []
    for tool_name, tc in all_tools.items():
        if tc.get("class") == "D" and not tc.get("subprocess"):
            class_d_no_sub.append(f"  {tool_name}")

    if class_d_no_sub:
        findings.append(
            "[WARN] docs/tool_contracts.json\n"
            "Class D tools should have subprocess:true (they open apps or run subprocesses):\n"
            + "\n".join(class_d_no_sub)
        )
    else:
        passes.append("[PASS] All Class D tools have subprocess:true")

    # — 6. Error prefix consistency —
    # Accepts: "{tool_name} failed:" OR "{tool_name} failed ({qualifier}):"
    # Excludes: helper functions like run_repo_command (matched by "Command failed")
    _VALID_ERR = _re.compile(r"[a-z_]+ failed[\s:(]")
    _SKIP_ERR = _re.compile(r"^Command failed|validate_orchestration_contract failed")
    tool_returns = _re.findall(r'return\s+f?"([^"]{5,80})"', server_text)
    bad_prefixes = [
        r for r in tool_returns
        if "failed" in r.lower()
        and not _VALID_ERR.match(r)
        and not _SKIP_ERR.match(r)
    ]
    if bad_prefixes:
        findings.append(
            "[WARN] mq-mcp/server.py\n"
            f"{len(bad_prefixes)} error return(s) don't use the '{{tool_name}} failed:' prefix pattern."
        )
    else:
        passes.append("[PASS] Error return prefix pattern is consistent")

    # — 7. Class C write tools not in any profile — NOTE only (by design for some) —
    # Some Class C tools (build_repo_context, record_architecture_decision) are
    # intentionally omitted from profiles; this surfaces unintentional omissions.
    class_c_tools = {n for n, tc in all_tools.items() if tc.get("class") == "C"}
    all_profile_tools: set[str] = set()
    try:
        for pf in sorted(profiles_dir.glob("*.json")):
            pd_ = _json.loads(pf.read_text(encoding="utf-8"))
            all_profile_tools.update(pd_.get("recommended_tools", []))
    except Exception:
        pass

    _INTENTIONALLY_PROFILE_FREE = {
        # All Class C tools require explicit user approval and are called
        # directly, not via automated profile-based workflows. Profiles list
        # Class A/B tools for agents; Class C tools are user-invoked.
        "build_repo_context", "record_architecture_decision",
        "extract_coding_conventions", "export_symbol_index",
        "bootstrap_semantic_memory", "store_semantic_memory",
        "update_repo_file", "edit_image", "take_screenshot", "set_clipboard",
    }
    uncovered = sorted(
        t for t in class_c_tools
        if t not in all_profile_tools and t not in _INTENTIONALLY_PROFILE_FREE
    )
    if uncovered:
        findings.append(
            "[WARN] profiles/\n"
            "Class C tools not in any profile and not in the expected-uncovered set: "
            + ", ".join(uncovered)
        )
    else:
        passes.append("[PASS] Class C tools covered by profiles or intentionally profile-free")

    # — Summary —
    pass_count = len(passes)
    fail_count = sum(1 for f in findings if f.startswith("[FAIL]"))
    warn_count = sum(1 for f in findings if f.startswith("[WARN]"))

    status = "PASS" if fail_count == 0 else "FAIL"
    header = (
        f"## Orchestration contract validation — {status}\n\n"
        f"Checks: {pass_count} passed, {fail_count} failed, {warn_count} warnings\n"
    )

    sections = []
    if passes:
        sections.append("\n".join(passes))
    if findings:
        sections.append("\n\n".join(findings))

    return header + "\n\n" + "\n\n".join(sections)


@mcp.tool()
def list_architecture_docs() -> str:
    """List all architecture documents with freshness status relative to server.py.

    Returns an inventory of docs/architecture/ showing each document's name,
    size, last-modified timestamp, and whether it is fresh (newer than server.py)
    or potentially stale (older). Use this to decide which architecture docs
    need review or update after server changes.

    Read-only. Requires no API key. Class A.
    """
    import datetime as _datetime

    arch_dir = REPO_ROOT / "docs" / "architecture"
    server_path = REPO_ROOT / "mq-mcp" / "server.py"

    if not arch_dir.exists():
        return "list_architecture_docs: docs/architecture/ directory not found."

    try:
        server_mtime = server_path.stat().st_mtime
    except Exception:
        server_mtime = None

    docs = sorted(arch_dir.glob("*.md"))
    if not docs:
        return "No .md files found in docs/architecture/."

    lines = ["# Architecture documents\n"]
    lines.append(f"{'Document':<40} {'Size':>8} {'Last modified':<24} Status")
    lines.append("-" * 90)

    for doc in docs:
        try:
            stat = doc.stat()
            size_kb = stat.st_size / 1024
            mtime = stat.st_mtime
            mtime_str = _datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

            if server_mtime is None:
                status = "unknown"
            elif mtime >= server_mtime:
                status = "fresh"
            else:
                hours_behind = (server_mtime - mtime) / 3600
                status = f"stale ({hours_behind:.0f}h behind server.py)"

            lines.append(f"{doc.name:<40} {size_kb:>7.1f}K {mtime_str:<24} {status}")
        except Exception as exc:
            lines.append(f"{doc.name:<40} {'?':>8} {'?':<24} error: {exc}")

    lines.append("")
    if server_mtime:
        server_ts = _datetime.datetime.fromtimestamp(server_mtime).strftime("%Y-%m-%d %H:%M")
        lines.append(f"Reference: server.py last modified {server_ts}")

    return "\n".join(lines)


@mcp.tool()
def review_architecture_doc(doc_name: str) -> str:
    """Review an architecture document against current runtime state.

    Applies the architecture review contract to the named document, injecting
    current runtime state (tool count, safety class breakdown, server.py
    last-modified) as context so the model can identify stale counts,
    incorrect safety classifications, and claims that no longer match the
    implementation.

    doc_name accepts:
      - bare name: "SYSTEM_OVERVIEW" (resolves to docs/architecture/SYSTEM_OVERVIEW.md)
      - with extension: "SYSTEM_OVERVIEW.md"
      - full path: "docs/architecture/SYSTEM_OVERVIEW.md"

    Requires OPENAI_API_KEY. Read-only. Class A.

    Args:
        doc_name: Name or path of the architecture document to review.
    """
    import ast as _ast
    import datetime as _datetime
    import re as _re
    import sys as _sys

    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    arch_dir = REPO_ROOT / "docs" / "architecture"
    server_path = REPO_ROOT / "mq-mcp" / "server.py"
    safety_path = REPO_ROOT / "docs" / "TOOL_SAFETY.md"

    # Resolve doc path
    candidates = [
        REPO_ROOT / doc_name,
        arch_dir / doc_name,
        arch_dir / (doc_name + ".md"),
    ]
    doc_path = next((p for p in candidates if p.exists()), None)
    if doc_path is None:
        available = [p.name for p in sorted(arch_dir.glob("*.md"))] if arch_dir.exists() else []
        avail_str = ", ".join(available) if available else "none"
        return (
            f"review_architecture_doc: '{doc_name}' not found.\n"
            f"Available in docs/architecture/: {avail_str}"
        )

    try:
        doc_text = doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"review_architecture_doc failed: could not read {doc_path.name}: {exc}"

    # Build runtime state context
    try:
        server_text = server_path.read_text(encoding="utf-8")
        tree = _ast.parse(server_text)
        tool_names: list[str] = []
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    attr = dec.func if isinstance(dec, _ast.Call) else dec
                    if (
                        isinstance(attr, _ast.Attribute)
                        and attr.attr == "tool"
                        and isinstance(attr.value, _ast.Name)
                        and attr.value.id == "mcp"
                    ):
                        tool_names.append(node.name)
        actual_count = len(tool_names)
    except Exception:
        tool_names = []
        actual_count = 0

    try:
        safety_text = safety_path.read_text(encoding="utf-8")
        m_section = _re.search(r"^## Summary table", safety_text, _re.MULTILINE)
        summary_section = safety_text[m_section.start():] if m_section else safety_text
        class_counts: dict[str, int] = {}
        for line in summary_section.splitlines():
            m = _re.match(r"^\|\s*`[a-z_]+`\s*\|\s*([A-D])\s*\|", line)
            if m:
                cls = f"Class {m.group(1)}"
                class_counts[cls] = class_counts.get(cls, 0) + 1
        class_summary = "  ".join(f"{k}: {v}" for k, v in sorted(class_counts.items()))
    except Exception:
        class_summary = "unavailable"

    try:
        server_mtime_str = _datetime.datetime.fromtimestamp(
            server_path.stat().st_mtime
        ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        server_mtime_str = "unknown"

    runtime_state = (
        f"## Current runtime state (injected for accuracy checking)\n\n"
        f"- Tool count: {actual_count}\n"
        f"- Safety class breakdown: {class_summary}\n"
        f"- server.py last modified: {server_mtime_str}\n"
        f"- Path resolvers: resolve_repo_file, resolve_allowed_local_file\n"
        f"- Tools: {', '.join(tool_names[:30])}"
        + (f" … (+{actual_count - 30} more)" if actual_count > 30 else "")
    )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return (
            f"review_architecture_doc: OPENAI_API_KEY not set.\n\n"
            f"Document: {doc_path.name}\n\n"
            f"{runtime_state}"
        )

    try:
        import openai as _openai

        arch_contract_path = REPO_ROOT / "reviews" / "contracts" / "architecture-review.md"
        arch_contract = (
            arch_contract_path.read_text(encoding="utf-8")
            if arch_contract_path.exists()
            else ""
        )

        system = (
            "You are a code review engine verifying an architecture document against "
            "the current runtime implementation.\n\n"
            "Follow the architecture review contract exactly. Output only structured "
            "findings in the format: [SEVERITY] file:location\\nbody\n\n"
            f"{arch_contract}\n\n"
            f"{runtime_state}"
        )
        user = (
            f"Review {doc_path.name} below.\n\n"
            "Identify:\n"
            "- Tool counts, version numbers, or statistics that do not match the "
            "runtime state above\n"
            "- Safety class claims inconsistent with the actual breakdown\n"
            "- Architectural claims that appear outdated or no longer accurate\n"
            "- Missing documentation for capabilities that now exist\n\n"
            "Do NOT flag accurate claims. Do NOT summarize. Output findings only.\n\n"
            f"```\n{doc_text}\n```"
        )

        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        client = _openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2048,
        )
        raw = (response.choices[0].message.content or "").strip()

        from review_engine.severity_engine import parse_findings, format_summary
        findings = parse_findings(raw)
        result = format_summary(findings, doc_path.name) if findings else raw

        return f"## {doc_path.name}\n\n{runtime_state}\n\n---\n\n{result}"

    except Exception as exc:
        return f"review_architecture_doc failed: {exc}"


@mcp.tool()
def list_architecture_decisions() -> str:
    """List all architecture memory entries (ADRs, boundaries, philosophy, rejected patterns).

    Returns a table with ID, status, category, and title for every entry in
    the architecture_memory/ directory. Use get_architecture_decision to read
    the full text of a specific entry.

    Args:
        None

    Safety: Class A — read-only, repo-scoped.
    """
    try:
        from review_engine.architecture_memory import ArchitectureMemory as _AM
        mem = _AM()
        entries = mem.list_all()
        if not entries:
            return "No architecture memory entries found."
        lines = [
            f"Architecture memory — {len(entries)} entries\n",
            f"{'ID':<10} {'Status':<12} {'Category':<12} Title",
            "-" * 72,
        ]
        for e in entries:
            lines.append(
                f"{e.get('id', ''):<10} {e.get('status', ''):<12} "
                f"{e.get('category', ''):<12} {e.get('title', '')}"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"list_architecture_decisions failed: {exc}"


@mcp.tool()
def get_architecture_decision(adr_id: str) -> str:
    """Return the full text of a specific architecture memory entry by ID.

    Args:
        adr_id: The entry ID, e.g. 'ADR-001', 'BND-001', 'PHI-001', 'REJ-001'.
                Case-insensitive.

    Safety: Class A — read-only, repo-scoped.
    """
    try:
        from review_engine.architecture_memory import ArchitectureMemory as _AM
        mem = _AM()
        text = mem.get(adr_id)
        if text is None:
            return f"No entry found for id '{adr_id}'. Use list_architecture_decisions to see all ids."
        return text
    except Exception as exc:
        return f"get_architecture_decision failed: {exc}"


@mcp.tool()
def record_architecture_decision(
    title: str,
    area: str,
    decision: str,
    rationale: str,
    consequences: str = "",
    category: str = "decisions",
) -> str:
    """Record a new architecture decision (ADR) in the architecture_memory/ store.

    Writes a new Markdown entry with YAML frontmatter. The entry is immediately
    available to list_architecture_decisions, get_architecture_decision, and the
    review_file context injector.

    Args:
        title:        Short descriptive title (e.g. 'Path resolvers are the only boundary').
        area:         Comma-separated keywords for file-path matching during review
                      injection (e.g. 'safety, server, paths').
        decision:     The decision itself — what was decided and what it means in practice.
        rationale:    Why this decision was made. Include constraints, trade-offs, incidents.
        consequences: Optional. What this decision implies for future work.
        category:     One of 'decisions', 'rejected', 'boundaries', 'philosophy'.
                      Defaults to 'decisions'.

    Safety: Class C — writes to architecture_memory/ inside the repo. Does not commit.
    Approval: Required — this tool writes a persistent file.
    """
    try:
        from review_engine.architecture_memory import ArchitectureMemory as _AM
        mem = _AM()
        adr_id = mem.record(
            title=title,
            area=area,
            decision=decision,
            rationale=rationale,
            consequences=consequences,
            category=category,
        )
        return (
            f"Recorded {adr_id}: {title}\n"
            f"Category: {category}  Area: {area}\n"
            f"File: architecture_memory/{category}/{adr_id.lower()}-*.md\n\n"
            f"Use get_architecture_decision('{adr_id}') to verify."
        )
    except Exception as exc:
        return f"record_architecture_decision failed: {exc}"


@mcp.tool()
def extract_coding_conventions(relative_path: str) -> str:
    """Extract generalizable coding conventions from the last review of a file
    and persist them into architecture_memory/decisions/ as convention entries.

    Conventions are rules that apply across multiple files — not one-off findings.
    They are injected into future reviews via the architecture decision context,
    giving the model codebase-specific guidance without repeating it in every prompt.

    Requires: the file must have at least one saved review (use review_file first).
    Requires: OPENAI_API_KEY must be set.

    Args:
        relative_path: Repo-relative path to the file whose last review to process.
                       E.g. "mq-mcp/server.py".

    Safety: Class C — reads review memory (repo-scoped), writes to
    architecture_memory/ (repo-scoped). Does not commit.
    Approval: Required — this tool writes persistent files.
    """
    try:
        from review_engine.review_memory import ReviewMemory as _ReviewMemory
        mem = _ReviewMemory()
        last = mem.get_last(relative_path)
        if last is None:
            return (
                f"No review found for '{relative_path}'. "
                "Run review_file first to generate findings."
            )
        findings_text = last.findings_text

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return "extract_coding_conventions requires OPENAI_API_KEY to be set."

        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        client = _openai.OpenAI(api_key=api_key)

        # Collect existing convention titles to avoid duplicates
        from review_engine.architecture_memory import ArchitectureMemory as _AM
        arch_mem = _AM()
        existing = arch_mem.list_all()
        existing_titles = [
            e["title"] for e in existing
            if e.get("status") == "convention"
        ]

        from review_engine.convention_extractor import ConventionExtractor as _CE
        extractor = _CE(client, model)
        conventions = extractor.extract(
            file_path=relative_path,
            findings_text=findings_text,
            existing_titles=existing_titles,
        )

        if not conventions:
            return (
                f"No generalizable conventions found in the last review of "
                f"'{relative_path}'. The findings may be file-specific or already "
                f"covered by existing conventions."
            )

        saved: list[str] = []
        for c in conventions:
            adr_id = arch_mem.record(
                title=c.convention,
                area=c.area,
                decision=c.convention,
                rationale=c.rationale,
                category="decisions",
                status="convention",
            )
            saved.append(f"  {adr_id}: {c.convention}")

        lines = [
            f"Extracted {len(saved)} convention(s) from '{relative_path}':",
            "",
        ] + saved + [
            "",
            "Conventions are now injected into future reviews of matching files.",
            "Use list_architecture_decisions to see all entries.",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return f"extract_coding_conventions failed: {exc}"


@mcp.tool()
def review_diff(mode: str = "comment", deep: bool = False) -> str:
    """Review all files changed in the working tree or staging area.

    Gets changed file paths from git diff, then runs review_file on each one.
    Only files with a supported extension (.py, .sh, .md, .json) are reviewed.
    Capped at 10 files per call. Requires OPENAI_API_KEY.

    Args:
        mode: Review mode passed to each review_file call. Defaults to 'comment'.
        deep: If True, runs multi-pass review for each file. Defaults to False.
    """
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
    except Exception as exc:
        return f"review_diff failed (git diff): {exc}"

    if not changed:
        try:
            proc = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
            )
            changed = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
        except Exception:
            pass

    if not changed:
        return "review_diff: no changed files found in working tree or staging area."

    reviewable_exts = {".py", ".sh", ".md", ".json"}
    from pathlib import Path as _Path
    files = [f for f in changed if _Path(f).suffix.lower() in reviewable_exts]

    if not files:
        return (
            f"review_diff: {len(changed)} changed file(s), none with reviewable "
            f"extensions ({', '.join(sorted(reviewable_exts))})."
        )

    MAX_FILES = 10
    truncated = len(files) > MAX_FILES
    files = files[:MAX_FILES]

    results = []
    for path in files:
        output = review_file(path, mode=mode, deep=deep)
        results.append(f"--- {path} ---\n{output}")

    header = f"review_diff: {len(files)} file(s) reviewed  mode={mode}  deep={deep}"
    if truncated:
        header += f"  [capped at {MAX_FILES}]"
    return header + "\n\n" + "\n\n".join(results)


@mcp.tool()
def risk_review_file(relative_path: str, mode: str = "security") -> str:
    """Targeted risk pass on a single file with a declared risk mode.

    Runs a grep-based pre-scan (detect_security_patterns) then an AI review
    under the matching contract. The pre-scan findings are injected into the
    model context before the file content so the model can cross-reference.

    Args:
        relative_path: Repo-relative path to the file.
        mode: One of 'security', 'risk', 'architecture'. Defaults to 'security'.
              security    — subprocess safety, injection, secret exposure, path traversal
              risk        — missing approval gates, undeclared side effects, stale contracts
              architecture — boundary violations, coupling, responsibility drift

    Returns:
        Structured findings using CRITICAL/RISK/WARNING/NOTE severity labels.

    Safety: Class A — read-only, no side effects beyond review memory write.
    """
    import openai as _openai
    import sys as _sys

    _VALID_RISK_MODES = {"security", "risk", "architecture"}
    if mode not in _VALID_RISK_MODES:
        return f"risk_review_file failed: mode must be one of {sorted(_VALID_RISK_MODES)}, got {mode!r}"

    try:
        target = resolve_repo_file(relative_path)
    except ValueError as exc:
        return f"risk_review_file blocked: {exc}"

    if not target.exists() or not target.is_file():
        return f"risk_review_file failed: file not found: {relative_path}"

    if target.stat().st_size > 200_000:
        return f"risk_review_file failed: file too large (> 200 KB): {relative_path}"

    try:
        file_content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"risk_review_file failed: could not read file: {exc}"

    contract = _load_review_contract(mode)
    if not contract:
        return f"risk_review_file failed: no contract for mode {mode!r}. Add reviews/contracts/{mode}-review.md."

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return "risk_review_file failed: OPENAI_API_KEY not set."

    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    # Pre-scan: grep-based pattern detection, no API call
    pre_scan = _detect_security_patterns(relative_path, file_content)

    # Load security skill for security/risk modes
    try:
        from review_engine.review_router import route_file_for_mode as _route_for_mode
        skill_name, skill_content = _route_for_mode(relative_path, mode)
    except Exception:
        skill_name, skill_content = "none", ""

    # Architecture role and past context
    arch_role = _load_architecture_role(relative_path)
    past_context = ""
    _mem = None
    try:
        from review_engine.review_memory import ReviewMemory as _ReviewMemory
        _mem = _ReviewMemory()
        past_context = _mem.format_past_context(relative_path)
    except Exception:
        pass

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    skill_section = f"\n\n## Skill: {skill_name}\n\n{skill_content}" if skill_content else ""
    role_context = f"\nArchitecture role: {arch_role}" if arch_role else ""
    past_section = f"\n\n## Previous review context\n\n{past_context}" if past_context else ""
    pre_scan_section = f"\n\n{pre_scan}" if pre_scan else "\n\nPre-scan: no pattern matches."

    system = (
        "You are a code review engine operating under a strict review contract.\n"
        "Follow the contract exactly. Do not deviate from the output format.\n"
        "Do not modify code. Output only structured review findings.\n\n"
        f"{contract}{skill_section}"
    )
    user = (
        f"Risk review — mode: {mode}\n\n"
        f"File: {relative_path}{role_context}{pre_scan_section}{past_section}\n\n"
        f"```\n{file_content}\n```"
    )

    try:
        client = _openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2048,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:
        return f"risk_review_file failed (API call): {exc}"

    if not raw:
        return "No review output."

    try:
        from review_engine.severity_engine import parse_findings, format_summary, severity_counts
        findings = parse_findings(raw)
        output = format_summary(findings, relative_path) if findings else raw
    except Exception:
        findings, output = [], raw

    try:
        if _mem is not None:
            from review_engine.severity_engine import severity_counts
            scounts = severity_counts(findings) if findings else {}
            _mem.save(
                file_path=relative_path,
                mode=f"risk:{mode}",
                findings_text=output,
                finding_count=len(findings),
                severity_counts=scounts,
                model=model,
                skill=skill_name,
            )
    except Exception:
        pass

    return output


@mcp.tool()
def risk_review_diff(mode: str = "security") -> str:
    """Risk pass over all files changed in the working tree or staging area.

    Runs risk_review_file on each changed file with the given mode. Gets
    changed files from git diff, filters to reviewable extensions, caps at 10.

    Args:
        mode: One of 'security', 'risk', 'architecture'. Defaults to 'security'.

    Safety: Class A — read-only, no side effects beyond review memory writes.
    """
    import subprocess as _sp

    _VALID_RISK_MODES = {"security", "risk", "architecture"}
    if mode not in _VALID_RISK_MODES:
        return f"risk_review_diff failed: mode must be one of {sorted(_VALID_RISK_MODES)}, got {mode!r}"

    try:
        proc = _sp.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
    except Exception as exc:
        return f"risk_review_diff failed (git diff): {exc}"

    if not changed:
        try:
            proc = _sp.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
            )
            changed = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
        except Exception:
            pass

    if not changed:
        return "risk_review_diff: no changed files in working tree or staging area."

    reviewable_exts = {".py", ".sh", ".md", ".json"}
    files = [f for f in changed if Path(f).suffix.lower() in reviewable_exts]

    if not files:
        return (
            f"risk_review_diff: {len(changed)} changed file(s), none with reviewable "
            f"extensions ({', '.join(sorted(reviewable_exts))})."
        )

    MAX_FILES = 10
    truncated = len(files) > MAX_FILES
    files = files[:MAX_FILES]

    results = []
    for path in files:
        output = risk_review_file(path, mode=mode)
        results.append(f"--- {path} ---\n{output}")

    header = f"risk_review_diff: {len(files)} file(s) reviewed  mode={mode}"
    if truncated:
        header += f"  [capped at {MAX_FILES}]"
    return header + "\n\n" + "\n\n".join(results)


@mcp.tool()
def store_semantic_memory(key: str, content: str, tags: str = "") -> str:
    """Store or update a knowledge item in semantic memory.

    Semantic memory is a durable, searchable knowledge layer for long-term
    reusable context — separate from per-file review history (review_engine/memory/)
    and architecture decisions (architecture_memory/).

    Items are stored in semantic_memory/store.json and injected into review_file
    context at priority 0 (above ADRs) when relevant to the file being reviewed.

    Args:
        key:     Unique identifier for this item (e.g. 'readme-summary', 'api-contract').
        content: The knowledge to store. Plain text, markdown, or structured notes.
        tags:    Optional comma-separated tags for search (e.g. 'readme,docs,mq-mcp').

    Safety: Class C — writes to semantic_memory/store.json. Does not commit.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from semantic_memory.semantic_memory import SemanticMemory as _SM
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        mem = _SM()
        item = mem.store(key, content, tag_list)
        tag_str = f"  tags: {', '.join(item.tags)}" if item.tags else ""
        return (
            f"store_semantic_memory: saved '{key}'{tag_str}\n"
            f"Total items: {mem.item_count()}"
        )
    except Exception as exc:
        return f"store_semantic_memory failed: {exc}"


@mcp.tool()
def search_semantic_memory(query: str, max_results: int = 5) -> str:
    """Search semantic memory by keywords across keys, tags, and content.

    Returns ranked matches with previews. Use this to retrieve cross-repo facts,
    doc summaries, contracts, and conventions stored via store_semantic_memory.

    Args:
        query:       Space-separated search terms.
        max_results: Maximum number of results to return (default 5, max 20).

    Safety: Class A — read-only.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from semantic_memory.semantic_memory import SemanticMemory as _SM
        cap = min(max(1, max_results), 20)
        mem = _SM()
        results = mem.search(query, max_results=cap)
        if not results:
            return f"search_semantic_memory: no results for '{query}' ({mem.item_count()} items in store)"
        lines = [f"search_semantic_memory: {len(results)} result(s) for '{query}'\n"]
        for item in results:
            tag_str = f"  [{', '.join(item.tags)}]" if item.tags else ""
            lines.append(f"### {item.key}{tag_str}\n{item.preview()}\n")
        return "\n".join(lines)
    except Exception as exc:
        return f"search_semantic_memory failed: {exc}"


@mcp.tool()
def get_semantic_memory(key: str) -> str:
    """Return the full content of a semantic memory item by exact key.

    Args:
        key: The exact key used when the item was stored.

    Safety: Class A — read-only.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from semantic_memory.semantic_memory import SemanticMemory as _SM
        mem = _SM()
        item = mem.get(key)
        if item is None:
            return f"get_semantic_memory: no item found for key '{key}'"
        tag_str = f"\nTags: {', '.join(item.tags)}" if item.tags else ""
        import datetime as _dt
        updated = _dt.datetime.fromtimestamp(item.updated_at).strftime("%Y-%m-%d %H:%M")
        return f"# {item.key}{tag_str}\nUpdated: {updated}\n\n{item.content}"
    except Exception as exc:
        return f"get_semantic_memory failed: {exc}"


@mcp.tool()
def list_semantic_memory() -> str:
    """List all items in semantic memory with key, tags, and content preview.

    Returns a table sorted by most recently updated first.

    Safety: Class A — read-only.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    try:
        from semantic_memory.semantic_memory import SemanticMemory as _SM
        import datetime as _dt
        mem = _SM()
        items = mem.list_all()
        if not items:
            return "list_semantic_memory: store is empty. Use store_semantic_memory to add items."
        lines = [f"# Semantic memory  ({len(items)} item(s))\n"]
        lines.append(f"{'Key':<40} {'Tags':<25} Updated")
        lines.append("-" * 80)
        for item in items:
            tags = ", ".join(item.tags) if item.tags else "—"
            updated = _dt.datetime.fromtimestamp(item.updated_at).strftime("%Y-%m-%d %H:%M")
            lines.append(f"{item.key:<40} {tags:<25} {updated}")
        return "\n".join(lines)
    except Exception as exc:
        return f"list_semantic_memory failed: {exc}"


@mcp.tool()
def bootstrap_semantic_memory() -> str:
    """Ingest key mq-mcp docs into semantic memory for use as review context.

    Bootstraps the store with summaries of the five highest-value documents:
    README.md, ROADMAP.md, docs/RUNTIME_CONTRACT.md,
    docs/ORCHESTRATION_CONTRACT.md, and docs/TOOL_SAFETY.md.

    Existing items are overwritten if the source doc has changed since last
    bootstrap (detected by content length difference).

    Safe to run multiple times — idempotent for unchanged docs.

    Safety: Class C — writes to semantic_memory/store.json. Does not commit.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    BOOTSTRAP_DOCS: list[tuple[str, str, list[str]]] = [
        ("readme-summary", "README.md", ["readme", "overview", "mq-mcp"]),
        ("roadmap-summary", "ROADMAP.md", ["roadmap", "phases", "mq-mcp"]),
        ("runtime-contract", "docs/RUNTIME_CONTRACT.md", ["contract", "runtime", "guarantees"]),
        ("orchestration-contract", "docs/ORCHESTRATION_CONTRACT.md", ["contract", "orchestration", "mq-agent"]),
        ("tool-safety", "docs/TOOL_SAFETY.md", ["safety", "tools", "classes"]),
    ]

    try:
        from semantic_memory.semantic_memory import SemanticMemory as _SM
        mem = _SM()
        saved = []
        skipped = []
        for key, rel_path, tags in BOOTSTRAP_DOCS:
            doc_path = REPO_ROOT / rel_path
            if not doc_path.exists():
                skipped.append(f"{key}: {rel_path} not found")
                continue
            content = doc_path.read_text(encoding="utf-8").strip()
            existing = mem.get(key)
            if existing and len(existing.content) == len(content):
                skipped.append(f"{key}: unchanged")
                continue
            mem.store(key, content, tags)
            saved.append(key)

        lines = [f"bootstrap_semantic_memory: {len(saved)} saved, {len(skipped)} skipped"]
        if saved:
            lines.append("Saved: " + ", ".join(saved))
        if skipped:
            lines.append("Skipped: " + ", ".join(skipped))
        lines.append(f"Total items in store: {mem.item_count()}")
        return "\n".join(lines)
    except Exception as exc:
        return f"bootstrap_semantic_memory failed: {exc}"


@mcp.tool()
def review_repo(mode: str = "comment", max_files: int = 5) -> str:
    """Review the least-recently-reviewed Python files in the repo.

    Uses review history to prioritize files that have never been reviewed or
    were reviewed longest ago. Falls back to all .py files if no history exists.
    Requires OPENAI_API_KEY.

    Args:
        mode: Review mode. Defaults to 'comment'.
        max_files: Number of files to review. Capped at 20. Defaults to 5.
    """
    import sys as _sys
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    cap = min(max(1, max_files), 20)

    ignore_parts = {"__pycache__", ".venv", "node_modules", ".git"}
    py_files = [
        str(p.relative_to(REPO_ROOT))
        for p in REPO_ROOT.rglob("*.py")
        if not any(part in ignore_parts or part.startswith(".") for part in p.parts[len(REPO_ROOT.parts):])
    ]

    if not py_files:
        return "review_repo: no Python files found in repo."

    history: dict[str, list[dict]] = {}
    try:
        from review_engine.review_memory import ReviewMemory as _ReviewMemory
        history = _ReviewMemory()._data
    except Exception:
        pass

    def last_ts(path: str) -> float:
        entries = history.get(path, [])
        return entries[0].get("timestamp", 0.0) if entries else 0.0

    to_review = sorted(py_files, key=last_ts)[:cap]

    results = []
    for path in to_review:
        output = review_file(path, mode=mode, deep=False)
        results.append(f"--- {path} ---\n{output}")

    header = f"review_repo: {len(to_review)} file(s) reviewed  mode={mode}"
    return header + "\n\n" + "\n\n".join(results)


@mcp.tool()
def export_symbol_index() -> str:
    """Write the current callgraph symbol map to generated/symbols/symbol_index.json.

    Exports the in-memory symbol index built by callgraph_builder to a
    repo-signal-compatible file so downstream tools can consume it without
    re-running the build.

    Output format: {schema, repo_name, generated_at, symbols{file_path: [name]}}

    Safety: Class C — writes to generated/symbols/symbol_index.json. Does not commit.
    """
    import sys as _sys
    from datetime import datetime as _dt, timezone as _tz
    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))

    cg_path = REPO_ROOT / "review_engine" / "context" / "callgraph.json"
    if not cg_path.exists():
        return "export_symbol_index failed: callgraph.json not found — run build_repo_context first."

    try:
        import json as _json
        cg = _json.loads(cg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"export_symbol_index failed: could not read callgraph.json: {exc}"

    out_dir = REPO_ROOT / "generated" / "symbols"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "symbol_index.json"

    payload = {
        "schema": "mq-mcp-symbol-index.v1",
        "repo_name": REPO_ROOT.name,
        "generated_at": _dt.now(_tz.utc).isoformat(),
        "symbols": cg.get("symbols", {}),
    }
    out_path.write_text(_json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    sym_count = sum(len(v) for v in payload["symbols"].values())
    return f"export_symbol_index: wrote {sym_count} symbols across {len(payload['symbols'])} files → generated/symbols/symbol_index.json"


@mcp.tool()
def repo_signal_status() -> str:
    """Report whether repo-signal export packs are present, their age, and merge status.

    Checks .repo-signal/exports/ for the four symbolic intelligence packs written
    by `repo-signal export` (callgraph.v1, symbol_index.v1, repo_summary.v1,
    risk_map.v1). Reports schema version and age of each file found.

    Run `repo-signal export` to generate or refresh packs.

    Safety: Class A — read-only, no side effects.
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    exports_dir = REPO_ROOT / ".repo-signal" / "exports"
    if not exports_dir.is_dir():
        return (
            "repo_signal_status: .repo-signal/exports/ not found.\n"
            "Run `repo-signal export` in the repo root to generate packs."
        )

    now = _dt.now(_tz.utc)
    pack_files = {
        "callgraph.json": "callgraph.v1",
        "symbol_index.json": "symbol_index.v1",
        "repo_summary.json": "repo_summary.v1",
        "risk_map.json": "risk_map.v1",
    }

    lines = [f"repo_signal_status: {exports_dir.relative_to(REPO_ROOT)}"]
    found_count = 0

    for filename, expected_schema in pack_files.items():
        fpath = exports_dir / filename
        if not fpath.exists():
            lines.append(f"  {filename:<25} NOT FOUND")
            continue
        mtime = _dt.fromtimestamp(fpath.stat().st_mtime, tz=_tz.utc)
        age_min = int((now - mtime).total_seconds() / 60)
        age_str = f"{age_min}m ago" if age_min < 120 else f"{age_min // 60}h ago"
        try:
            schema = _json.loads(fpath.read_text(encoding="utf-8")).get("schema", "?")
        except Exception:
            schema = "unreadable"
        status = "OK" if schema == expected_schema else f"SCHEMA MISMATCH (got {schema!r})"
        lines.append(f"  {filename:<25} [{schema}]  {age_str}  {status}")
        if schema == expected_schema:
            found_count += 1

    cg_path = REPO_ROOT / "review_engine" / "context" / "callgraph.json"
    if cg_path.exists():
        try:
            merged_status = _json.loads(cg_path.read_text(encoding="utf-8")).get(
                "repo_signal_status", "not recorded"
            )
        except Exception:
            merged_status = "unreadable"
        lines.append(f"\nLast merge: {merged_status}")
    else:
        lines.append("\nMerge: callgraph.json not built yet — run build_repo_context first.")

    lines.append(f"\n{found_count}/{len(pack_files)} packs valid.")
    return "\n".join(lines)


# ─── Learn Layer ──────────────────────────────────────────────────────────────

def _learn_engine():
    """Lazy-import learn_engine so server still starts if file is missing."""
    import importlib.util, sys as _sys
    mod_path = Path(__file__).parent / "learn_engine.py"
    if not mod_path.exists():
        raise RuntimeError("learn_engine.py not found")
    if "learn_engine" in _sys.modules:
        return _sys.modules["learn_engine"]
    spec = importlib.util.spec_from_file_location("learn_engine", mod_path)
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["learn_engine"] = mod
    spec.loader.exec_module(mod)
    return mod


@mcp.tool()
def record_learning(
    task: str,
    lesson: str,
    validation: str,
    source: str = "manual",
    repo: str = "",
    risk: str = "low",
    tags: str = "",
) -> str:
    """Store a verified engineering lesson in the local learn layer.

    Secrets are redacted before storage. The lesson is never automatically
    promoted to AGENTS.md, CLAUDE.md, or any config file.

    Args:
        task:       What was being done (e.g. "fix version drift in CI").
        lesson:     What was learned (e.g. "pyproject.toml must match VERSION").
        validation: How the lesson was verified (e.g. "CI green after fix").
        source:     Origin — codex | claude | mq-agent | mq-hal | manual |
                    review | diff.
        repo:       Repo name this applies to (empty = general).
        risk:       low | medium | high | unknown.
        tags:       Comma-separated tags (e.g. "ci,docs,release").

    Safety: Class A — local write to REPO_ROOT/learn_engine/memory/lessons.jsonl,
    no command execution, no allowlist mutation.
    """
    eng = _learn_engine()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    record = eng.make_learning(
        REPO_ROOT,
        repo=repo or "",
        source=source,
        task=task,
        lesson=lesson,
        validation=validation,
        tags=tag_list,
        risk=risk,
    )
    result = eng.record_learning(REPO_ROOT, record)
    return (
        f"Saved lesson {result['id']}.\n"
        f"  repo:   {result['repo'] or '(general)'}\n"
        f"  source: {result['source']}\n"
        f"  risk:   {result['risk']}\n"
        f"  task:   {result['task'][:72]}"
    )


@mcp.tool()
def list_learnings(repo: str = "", source: str = "", risk: str = "") -> str:
    """List stored engineering lessons, with optional filters.

    Args:
        repo:   Filter by repo name (empty = all).
        source: Filter by source (empty = all).
        risk:   Filter by risk level — low | medium | high | unknown (empty = all).

    Safety: Class A — read-only.
    """
    eng = _learn_engine()
    lessons = eng.load_learnings(REPO_ROOT)

    if repo:
        lessons = [l for l in lessons if l.get("repo") == repo]
    if source:
        lessons = [l for l in lessons if l.get("source") == source]
    if risk:
        lessons = [l for l in lessons if l.get("risk") == risk]

    if not lessons:
        return "No lessons found."

    lines = [f"Found {len(lessons)} lesson(s):\n"]
    for l in lessons:
        ts = str(l.get("created_at", ""))[:16]
        lid = l.get("id", "?")
        repo_name = (l.get("repo") or "(general)")[:16]
        src = (l.get("source") or "-")[:8]
        task = str(l.get("task", ""))[:60]
        lines.append(f"[{lid}]  {ts}  {src:8}  {repo_name:16}  {task}")

    return "\n".join(lines)


@mcp.tool()
def get_learning(learning_id: str) -> str:
    """Show a single stored lesson by id (prefix match).

    Args:
        learning_id: Full id or unique prefix (e.g. "learn_20260531_0001").

    Safety: Class A — read-only.
    """
    eng = _learn_engine()
    lessons = eng.load_learnings(REPO_ROOT)
    matches = [l for l in lessons if l.get("id", "").startswith(learning_id)]

    if not matches:
        return f"No lesson found with id starting with {learning_id!r}."
    if len(matches) > 1:
        ids = ", ".join(l["id"] for l in matches)
        return f"Ambiguous prefix {learning_id!r} — matches: {ids}"

    l = matches[0]
    lines = [
        f"Lesson: {l.get('id')}",
        f"Created:    {l.get('created_at', '-')}",
        f"Repo:       {l.get('repo') or '(general)'}",
        f"Source:     {l.get('source', '-')}",
        f"Risk:       {l.get('risk', '-')}",
        "",
        "Task",
        "----",
        str(l.get("task", "")),
        "",
        "Lesson",
        "------",
        str(l.get("lesson", "")),
    ]
    if l.get("validation"):
        val = l["validation"]
        if isinstance(val, list):
            val = "; ".join(val)
        lines += ["", "Validation", "----------", str(val)]
    if l.get("tags"):
        lines.append(f"\nTags: {', '.join(l['tags'])}")

    return "\n".join(lines)


@mcp.tool()
def search_learnings(query: str, repo: str = "") -> str:
    """Full-text search across stored lessons (task, lesson, validation, repo).

    Args:
        query: Search term (case-insensitive).
        repo:  Limit to a specific repo (empty = all).

    Safety: Class A — read-only.
    """
    eng = _learn_engine()
    results = eng.search_learnings(REPO_ROOT, query)

    if repo:
        results = [l for l in results if l.get("repo") == repo]

    if not results:
        return f"No lessons matched {query!r}."

    lines = [f"Found {len(results)} match(es) for {query!r}:\n"]
    for l in results:
        lid = l.get("id", "?")
        src = (l.get("source") or "-")[:8]
        repo_name = (l.get("repo") or "(general)")[:16]
        task = str(l.get("task", ""))[:60]
        lines.append(f"[{lid}]  {src:8}  {repo_name:16}  {task}")

    return "\n".join(lines)


@mcp.tool()
def summarize_learnings(repo: str = "", limit: int = 20) -> str:
    """Summarize stored lessons — counts by source and risk, recent entries.

    Args:
        repo:  Limit to a specific repo (empty = all).
        limit: Max number of recent lessons to show in the summary (default 20).

    Safety: Class A — read-only.
    """
    eng = _learn_engine()
    return eng.summarize_learnings(REPO_ROOT, limit=limit)


@mcp.tool()
def promote_learning(learning_id: str, target: str) -> str:
    """Preview how a lesson would look if promoted to a target document.

    Does NOT write any files. Returns a formatted preview of the content
    that could be manually copied to the target.

    Args:
        learning_id: Lesson id (full or prefix).
        target:      Destination — runbook | agents-md | claude-md |
                     architecture-memory.

    Safety: Class A — read-only preview, no file writes.
    """
    eng = _learn_engine()
    return eng.promotion_preview(REPO_ROOT, learning_id, target)


# ─── mqlaunch ─────────────────────────────────────────────────────────────────

_ANSI_ESC = re.compile(r"\x1b\[[0-9;]*[mABCDEFGHJKSThlrs]|\x1b\[[0-9;]*[a-zA-Z]|\x1b[=>]|\r")
_TUI_SPLASH = re.compile(r"PHOSPHOR GRID|███|╔═|╚═|═══")


def _run_mqlaunch(*args: str, timeout: int = 15) -> tuple[str, int]:
    """Run a mqlaunch command headless. Returns (clean_output, returncode)."""
    env = {**os.environ, "TERM": "xterm", "COLUMNS": "120", "LINES": "40"}
    try:
        result = subprocess.run(
            ["mqlaunch", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        raw = result.stdout + result.stderr
        clean = _ANSI_ESC.sub("", raw)
        return clean.strip(), result.returncode
    except FileNotFoundError:
        return "ERROR: mqlaunch not found on PATH.", 127
    except subprocess.TimeoutExpired:
        return f"ERROR: mqlaunch {' '.join(args)} timed out after {timeout}s.", 1


def _is_tui_output(text: str) -> bool:
    return bool(_TUI_SPLASH.search(text))


@mcp.tool()
def run_mqlaunch_doctor() -> str:
    """Run mqlaunch doctor — environment and dependency health check.

    Returns a structured pass/fail report of all tool dependencies, PATH
    entries, and runtime prerequisites.

    Output quality: GOOD — structured PASS/FAIL/WARN lines, machine-readable.
    No limitations in headless mode.

    Safety: Class A — read-only diagnostic, no side effects.
    """
    output, rc = _run_mqlaunch("doctor")
    status = "exit 0 (healthy)" if rc == 0 else f"exit {rc} (issues found)"
    return f"mqlaunch doctor [{status}]\n\n{output}"


@mcp.tool()
def run_mqlaunch_selftest() -> str:
    """Run mqlaunch selftest — internal smoke tests for mqlaunch itself.

    Verifies that mqlaunch's internal bridges, legacy launchers, and tool
    routes are intact.

    Output quality: GOOD — [PASS]/[FAIL] lines, clean in headless mode.
    No limitations.

    Safety: Class A — read-only smoke checks.
    """
    output, rc = _run_mqlaunch("selftest")
    status = "exit 0 (all pass)" if rc == 0 else f"exit {rc} (failures)"
    return f"mqlaunch selftest [{status}]\n\n{output}"


@mcp.tool()
def run_mqlaunch_release_check() -> str:
    """Run mqlaunch release-check — pre-release gate for macos-scripts.

    Checks release readiness: version sync, changelog, CI status, doctor.

    Output quality: GOOD — structured PASS/FAIL per check.
    No limitations in headless mode.

    Safety: Class A — read-only checks, no commits or pushes.
    """
    output, rc = _run_mqlaunch("release-check")
    status = "exit 0 (ready)" if rc == 0 else f"exit {rc} (not ready)"
    return f"mqlaunch release-check [{status}]\n\n{output}"


@mcp.tool()
def run_mqlaunch_version() -> str:
    """Run mqlaunch version — show mqlaunch version information.

    Output quality: LIMITED — outputs large ASCII-art splash screen. The
    version string is buried inside TUI output and not cleanly parseable.

    Limitation: mqlaunch version has no --plain or --json flag.
    Fix: add `mqlaunch version --plain` that outputs a bare version string,
    e.g. `mqlaunch 2.4.1`.

    Safety: Class A — read-only.
    """
    output, rc = _run_mqlaunch("version")
    if _is_tui_output(output):
        version_line = next(
            (l for l in output.splitlines() if re.search(r"\d+\.\d+\.\d+", l)),
            None,
        )
        note = (
            f"NOTE: Output is TUI splash — version extracted heuristically.\n"
            f"Fix: add `mqlaunch version --plain` for a bare version string.\n\n"
        )
        return note + (version_line or output[:400])
    return output


@mcp.tool()
def run_mqlaunch_system_check() -> str:
    """Run mqlaunch system check — system health and environment overview.

    Output quality: LIMITED — launches a TUI login/boot screen with ANSI
    graphics. Useful status info (MEM, BAT, HOST, USER) is embedded in the
    splash but not cleanly separable.

    Limitation: no `--no-tui` or `--json` flag. Command opens an interactive
    screen rather than printing a parseable report.
    Fix: add `mqlaunch system check --json` returning a JSON object with
    {user, host, mem_pct, bat_pct, state, severity} fields.

    Safety: Class A — read-only.
    """
    output, rc = _run_mqlaunch("system", "check")
    if _is_tui_output(output):
        lines = [l for l in output.splitlines() if l.strip() and not _TUI_SPLASH.search(l)]
        return (
            "NOTE: Output is TUI splash — structured data not available headless.\n"
            "Fix: add `mqlaunch system check --json` for machine-readable output.\n\n"
            + "\n".join(lines[:30])
        )
    return output


@mcp.tool()
def run_mqlaunch_perf() -> str:
    """Run mqlaunch perf — performance monitoring menu.

    Output quality: LIMITED — opens an interactive TUI performance menu.
    No parseable output is produced in headless mode.

    Limitation: `mqlaunch perf` is a TUI entry point, not a non-interactive
    report command. It requires a real terminal to display CPU/MEM/disk graphs.
    Fix: add `mqlaunch perf --report` that outputs a plain-text or JSON
    snapshot of current CPU, memory, disk and network usage without the TUI.

    Safety: Class A — read-only performance sampling.
    """
    output, rc = _run_mqlaunch("perf")
    if _is_tui_output(output):
        lines = [l for l in output.splitlines() if l.strip() and not _TUI_SPLASH.search(l)]
        return (
            "NOTE: `mqlaunch perf` is a TUI menu — no parseable output in headless mode.\n"
            "Fix: add `mqlaunch perf --report` for a non-interactive performance snapshot.\n\n"
            + ("\n".join(lines[:20]) if lines else "(no readable content captured)")
        )
    return output


@mcp.tool()
def run_mqlaunch_demo() -> str:
    """Run mqlaunch demo — guided demo of mqlaunch features.

    Output quality: LIMITED — outputs TUI splash and then waits for
    interactive input. In headless mode it times out after a short wait.

    Limitation: demo mode is interactive by design. No headless equivalent.
    Fix: add `mqlaunch demo --script` that runs the demo non-interactively
    and prints a transcript, useful for CI and MCP contexts.

    Safety: Class A — read-only demonstration.
    """
    output, rc = _run_mqlaunch("demo", timeout=6)
    if _is_tui_output(output) or not output.strip():
        return (
            "NOTE: `mqlaunch demo` is an interactive TUI — no parseable output headless.\n"
            "Fix: add `mqlaunch demo --script` for a non-interactive demo transcript."
        )
    return output


@mcp.tool()
def run_mqlaunch_bundle() -> str:
    """Run mqlaunch bundle — create a debug bundle for support/diagnostics.

    Output quality: LIMITED — launches TUI. In a real terminal this would
    create a `.tar.gz` debug bundle; headless it only shows the splash screen.

    Limitation: bundle creation is TUI-gated. The output path is not reported
    to stdout in headless mode.
    Fix: add `mqlaunch bundle --out <path>` that writes the bundle to a
    specified path and prints the path on stdout for programmatic use.

    Safety: Class B — creates a local file, no network calls.
    """
    output, rc = _run_mqlaunch("bundle", timeout=10)
    if _is_tui_output(output):
        return (
            "NOTE: `mqlaunch bundle` is TUI-gated — bundle was NOT created headless.\n"
            "Fix: add `mqlaunch bundle --out <path>` for non-interactive bundle creation."
        )
    return output


@mcp.tool()
def run_mqlaunch_ask(question: str) -> str:
    """Ask mqlaunch a natural-language question about the current repo.

    Output quality: BROKEN headless — without OPENAI_API_KEY set, mqlaunch
    copies a prompt to the clipboard instead of answering. With the key set
    it calls the OpenAI API and returns a direct answer.

    Limitation: requires `OPENAI_API_KEY` env var. Without it, the command
    silently routes to a clipboard-copy fallback that is useless in MCP context.
    Fix 1: set OPENAI_API_KEY in the environment before calling this tool.
    Fix 2: add `mqlaunch ask --no-clipboard` that errors explicitly instead
    of silently falling back to clipboard.

    Args:
        question: Natural-language question about the repo.

    Safety: Class C — reads local files, calls OpenAI API if key is set.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return (
            "ERROR: OPENAI_API_KEY is not set.\n"
            "`mqlaunch ask` requires the OpenAI API key to answer questions.\n"
            "Without it, mqlaunch silently copies a prompt to the clipboard.\n\n"
            "Fix 1: set OPENAI_API_KEY in the environment.\n"
            "Fix 2: use `search_repo` or `read_repo_file` for local repo queries."
        )
    output, rc = _run_mqlaunch("ask", question, timeout=30)
    if "Copied" in output and "clipboard" in output:
        return (
            "ERROR: mqlaunch routed to clipboard-copy fallback.\n"
            "This typically means OPENAI_API_KEY is missing or not visible to mqlaunch.\n"
            f"Raw output: {output}"
        )
    return output


if __name__ == "__main__":
    transport = os.getenv("MQ_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)  # type: ignore[arg-type]
