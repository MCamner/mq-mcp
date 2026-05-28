"""
Review Router — mq-mcp review engine, Phase 2.2

Routes a file to the correct review skill based on extension and path.
Returns the skill content to inject into a review prompt.

Usage:
  from review_engine.review_router import route_file
  skill_text = route_file("mq-mcp/server.py")
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "reviews" / "skills"

# Routing table: (path_pattern, extension_set) → skill filename
# Checked in order — first match wins.
_ROUTES: list[tuple[str | None, set[str], str]] = [
    # MCP tool definitions — matched by content pattern in path
    ("mq-mcp/server.py",  {".py"},  "mcp-tool-review.md"),
    # Shell scripts
    (None,                {".sh"},  "shell-review.md"),
    # Python source
    (None,                {".py"},  "python-comment-review.md"),
    # Markdown documentation
    (None,                {".md"},  "markdown-review.md"),
    # JSON config and metadata
    (None,                {".json"}, "json-review.md"),
]


# Security-mode skill: always injected for security and risk modes regardless of file type.
_SECURITY_SKILL_FILE = "security-review.md"


def route_file_for_mode(relative_path: str, mode: str) -> tuple[str, str]:
    """Like route_file but injects the security skill for security and risk modes."""
    if mode in {"security", "risk"}:
        skill_path = SKILLS_DIR / _SECURITY_SKILL_FILE
        if skill_path.exists():
            return _SECURITY_SKILL_FILE.replace(".md", ""), skill_path.read_text(encoding="utf-8")
    return route_file(relative_path)


def route_file(relative_path: str) -> tuple[str, str]:
    """
    Return (skill_name, skill_content) for the given repo-relative file path.

    Falls back to ("none", "") if no skill matches.

    Args:
        relative_path: Repo-relative path to the file being reviewed.
    """
    suffix = Path(relative_path).suffix.lower()

    for path_pattern, extensions, skill_file in _ROUTES:
        if suffix not in extensions:
            continue
        if path_pattern is not None and path_pattern not in relative_path:
            continue

        skill_path = SKILLS_DIR / skill_file
        if not skill_path.exists():
            continue

        return skill_file.replace(".md", ""), skill_path.read_text(encoding="utf-8")

    return "none", ""


def list_routes() -> list[dict]:
    """Return all configured routes with their match criteria and skill availability."""
    result = []
    for path_pattern, extensions, skill_file in _ROUTES:
        skill_path = SKILLS_DIR / skill_file
        result.append({
            "path_pattern": path_pattern or "*",
            "extensions": sorted(extensions),
            "skill": skill_file,
            "available": skill_path.exists(),
        })
    return result


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
        name, content = route_file(path)
        print(f"Skill: {name}")
        if content:
            print(f"--- skill content ({len(content)} chars) ---")
            print(content[:500] + ("..." if len(content) > 500 else ""))
        else:
            print("No skill matched.")
    else:
        print("Configured routes:")
        print(json.dumps(list_routes(), indent=2))
