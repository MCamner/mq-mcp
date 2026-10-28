"""TTY-only visual components for Bridget's interactive chat.

The renderers in this module are deliberately pure: they return text and never
touch the terminal themselves.  ``bridge.py`` decides when a real TTY is
available, which keeps pipes, captured output, CI, and automation free from
ANSI control bytes.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from collections.abc import Iterable

BOX_WIDTH = 62
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_AMBER = "\x1b[38;2;255;190;98m"
_CYAN = "\x1b[38;2;132;191;196m"
_RED = "\x1b[38;2;240;128;128m"
_DIM = "\x1b[2m"
_RESET = "\x1b[0m"


def terminal_width(value: str) -> int:
    """Return the number of terminal columns used by printable ``value``."""
    plain = _ANSI_ESCAPE.sub("", value)
    return sum(
        0 if unicodedata.combining(char) else
        2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        for char in plain
    )


def _safe(value: object) -> str:
    """Remove terminal control characters from dynamic display data."""
    plain = _ANSI_ESCAPE.sub("", str(value))
    return "".join(
        char
        for char in plain
        if char in ("\n", "\t")
        or (char.isprintable() and not unicodedata.category(char).startswith("C"))
    )


def _truncate(value: object, columns: int) -> str:
    text = _safe(value).replace("\n", " ").replace("\t", " ")
    if terminal_width(text) <= columns:
        return text
    suffix = "…"
    while text and terminal_width(text + suffix) > columns:
        text = text[:-1]
    return text.rstrip() + suffix


def _pad(value: str, columns: int) -> str:
    return value + " " * max(0, columns - terminal_width(value))


def _row(value: str = "", *, width: int = BOX_WIDTH) -> str:
    return "│ " + _pad(_truncate(value, width - 2), width - 2) + " │"


def _title_border(title: str, *, width: int = BOX_WIDTH) -> str:
    label = _truncate(f"─ {title} ", width)
    return "╭" + label + "─" * max(0, width - terminal_width(label)) + "╮"


def _bottom_border(*, width: int = BOX_WIDTH) -> str:
    return "╰" + "─" * width + "╯"


def _console_width() -> int:
    return max(12, min(74, shutil.get_terminal_size((80, 24)).columns - 2))


def _tint(value: str, shade: str, color: bool) -> str:
    return f"{shade}{value}{_RESET}" if color else value


def render_session_card(
    name: str,
    *,
    model: str,
    tool_count: int,
    project: str | None = None,
    branch: str | None = None,
    color: bool = False,
) -> str:
    """Compact session header; terminal background belongs to the operator."""
    width = _console_width()
    location = project or "ingen vald"
    if branch:
        location += "/" + branch
    lines = [
        _title_border("◉‿◉ Bridget", width=width - 2),
        _row(f"{location}   ● MCP ansluten", width=width - 2),
        _bottom_border(width=width - 2),
        _truncate(f"Hej {name}.  {model}  ·  {tool_count} verktyg  ·  /help", width),
    ]
    if color:
        lines[0] = lines[0].replace("◉‿◉ Bridget", _tint("◉‿◉ Bridget", _AMBER, True))
        lines[1] = lines[1].replace("●", _tint("●", _CYAN, True), 1)
    return "\n".join(lines) + "\n"


def render_hud(
    *,
    project: str | None,
    branch: str | None,
    tool_count: int,
    context_percent: int,
    color: bool = False,
    model: str = "",
) -> str:
    """Status strip printed before input, preserving native scrollback."""
    width = _console_width()
    percent = max(0, min(100, context_percent))
    filled = round(percent * 8 / 100)
    bar = "▰" * filled + "▱" * (8 - filled)
    state = f"Kontext {bar} {percent}%"
    left = _truncate(model or project or "Bridget", max(4, width - len(state) - 12))
    text = _truncate(f"{left}   {state}   /help", width)
    if color:
        text = text.replace(bar, _tint(bar, _AMBER, True))
    return "\n" + _tint("─" * width, _DIM, color) + "\n" + text + "\n"


def render_tool_activity(name: str, *, failed: bool = False, color: bool = False) -> str:
    """One completed tool result, never treating errors as successes."""
    status = "✕ misslyckades" if failed else "✓ klart"
    status = _tint(status, _RED if failed else _CYAN, color)
    label = _truncate(name, max(4, _console_width() - 24))
    return f"    └─ {label}  {status}\n"


def render_tool_running(name: str, *, color: bool = False) -> str:
    label = _truncate(name, max(4, _console_width() - 14))
    return "\r" + _tint("◉_◉", _AMBER, color) + f" Kör {label}…"


def render_tool_summary(tool_names: Iterable[str], *, color: bool = False) -> str:
    """Collapse completed tool calls to one calm, inspectable line."""
    names = [_safe(name) for name in tool_names if name]
    if not names:
        return ""
    shown = names[:3]
    suffix = f" +{len(names) - 3}" if len(names) > 3 else ""
    return "    Anrop: " + ", ".join(shown) + suffix + "\n"


def render_response_card(answer: str, *, color: bool = False) -> str:
    """Open, column-aware response; preserve indentation and every wide glyph."""
    width = _console_width() - 4
    lines = ["", _tint("◉‿◉ Bridget", _AMBER, color)]
    for paragraph in (_safe(answer).strip("\n") or "…").expandtabs(4).splitlines():
        while terminal_width(paragraph) > width:
            end = 0
            columns = 0
            for char in paragraph:
                size = terminal_width(char)
                if columns + size > width:
                    break
                columns += size
                end += 1
            # Prefer a word boundary, but never drop an unbroken wide string.
            space = paragraph.rfind(" ", 0, end + 1)
            if space > len(paragraph) - len(paragraph.lstrip()):
                end = space
                lines.append("    " + paragraph[:end])
                paragraph = paragraph[end + 1:]
            else:
                lines.append("    " + paragraph[:end])
                paragraph = paragraph[end:]
        lines.append("    " + paragraph if paragraph else "")
    return "\n".join(lines) + "\n\n"


def render_help_card(*, color: bool = False) -> str:
    """Render Bridget's local command palette."""
    title = "KOMMANDON"
    if color:
        title = f"{_CYAN}{title}{_RESET}"
    lines = [
        _title_border(title),
        _row("/status   visa session, modell, repo och verktyg"),
        _row("/clear    rensa skärmen och rita om Bridget"),
        _row("/face     visa Bridget"),
        _row("/help     visa den här kommandopaletten"),
        _row("/exit     avsluta chatten"),
        _bottom_border(),
    ]
    return "\n".join(lines) + "\n"


def thinking_frame(frame: str, *, color: bool = False) -> str:
    """Return one in-place activity frame for the spinner thread."""
    face = "◉_◉"
    if color:
        face = f"{_AMBER}{face}{_RESET}"
        frame = f"{_CYAN}{frame}{_RESET}"
    return f"\r{face} Bridget tänker {frame}"


def clear_screen_sequence() -> str:
    """ANSI clear-screen sequence, kept explicit and TTY-gated by the caller."""
    return "\x1b[2J\x1b[H"
