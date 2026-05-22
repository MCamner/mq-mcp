import random
import requests
import os
from pathlib import Path
import psutil
import shutil
import subprocess
import pandas as pd
import guitarpro
from PIL import Image
from mcp.server.fastmcp import FastMCP

# Initiera servern
mcp = FastMCP("mq-mcp")

REPO_ROOT = Path(__file__).resolve().parent.parent

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
            if action == "rotate": img = img.rotate(value or 90, expand=True)
            elif action == "grayscale": img = img.convert("L")
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


if __name__ == "__main__":
    mcp.run()
