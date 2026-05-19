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


def allowed_external_roots() -> list[Path]:
    """Return explicit external roots allowed for media/app file tools.

    Configure with:
      MQ_MCP_ALLOWED_PATHS="/Users/mansys/Music:/Users/mansys/Pictures"
    """
    raw = os.getenv("MQ_MCP_ALLOWED_PATHS", "")
    roots: list[Path] = []
    for item in raw.split(":"):
        item = item.strip()
        if item:
            roots.append(Path(item).expanduser().resolve())
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

if __name__ == "__main__":
    mcp.run()
