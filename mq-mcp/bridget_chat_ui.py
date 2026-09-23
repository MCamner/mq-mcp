"""TTY-only visual components for Bridget's interactive chat.

The renderers in this module are deliberately pure: they return text and never
touch the terminal themselves.  ``bridge.py`` decides when a real TTY is
available, which keeps pipes, captured output, CI, and automation free from
ANSI control bytes.
"""

from __future__ import annotations

import re
import textwrap
import unicodedata
from collections.abc import Iterable

BOX_WIDTH = 62
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_AMBER = "\x1b[33m"
_CYAN = "\x1b[36m"
_GREEN = "\x1b[32m"
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
    label = f"─ {title} "
    return "╭" + label + "─" * max(0, width - terminal_width(label)) + "╮"


def _bottom_border(*, width: int = BOX_WIDTH) -> str:
    return "╰" + "─" * width + "╯"


def render_session_card(
    name: str,
    *,
    model: str,
    tool_count: int,
    project: str | None = None,
    branch: str | None = None,
    color: bool = False,
) -> str:
    """Render the reveal card shown after MCP session initialization."""
    face = "◉‿◉"
    online = "ONLINE"
    ready = "READY"

    location = _safe(project or "ingen vald")
    if branch:
        location += "/" + _safe(branch)
    lines = [
        _title_border("BRIDGET"),
        _row(f"{face}  Hej {_safe(name)}."),
        _row(),
        _row(f"MCP ........ {online}"),
        _row(f"Memory ..... {ready}"),
        _row(f"Tools ...... {tool_count}"),
        _row(f"Model ...... {_safe(model)}"),
        _row(f"Repo ....... {location}"),
        _row(),
        _row("Session initialized  •  /help visar kommandon"),
        _bottom_border(),
    ]
    card = "\n".join(lines) + "\n"
    if color:
        # Colour only after all width-sensitive framing is complete. Dynamic
        # values are already sanitized, and escape bytes must not be counted as
        # terminal columns or stripped by the row helpers.
        card = card.replace("◉‿◉", f"{_AMBER}◉‿◉{_RESET}", 1)
        card = card.replace("ONLINE", f"{_GREEN}ONLINE{_RESET}", 1)
        card = card.replace("READY", f"{_GREEN}READY{_RESET}", 1)
    return card


def render_hud(
    *,
    project: str | None,
    branch: str | None,
    tool_count: int,
    context_percent: int,
    color: bool = False,
) -> str:
    """Render the compact one-line state bar shown before each prompt."""
    repo = _safe(project or "no-project")
    if branch:
        repo += "/" + _safe(branch)
    dot = "●"
    text = (
        f"─ {_truncate(repo, 22)} ── {dot} MCP ── tools:{tool_count} "
        f"── ctx:{max(0, min(100, context_percent))}% ─"
    )
    text = _truncate(text, BOX_WIDTH)
    hud = "╭" + _pad(text, BOX_WIDTH) + "╮\n"
    if color:
        hud = hud.replace("●", f"{_GREEN}●{_RESET}", 1)
    return hud


def render_tool_summary(tool_names: Iterable[str], *, color: bool = False) -> str:
    """Collapse completed tool calls to one calm, inspectable line."""
    names = [_safe(name) for name in tool_names if name]
    if not names:
        return ""
    shown = names[:3]
    suffix = f" +{len(names) - 3}" if len(names) > 3 else ""
    check = f"{_GREEN}✓{_RESET}" if color else "✓"
    return f"{check} tools  " + " → ".join(shown) + suffix + "\n"


def render_response_card(answer: str, *, color: bool = False) -> str:
    """Render Bridget's answer as a wrapped terminal message card."""
    sprite = "▚█▞"
    if color:
        sprite = f"{_AMBER}{sprite}{_RESET}"
    lines = [_title_border(f"{sprite} Bridget")]
    safe_answer = _safe(answer).strip() or "…"
    for paragraph in safe_answer.splitlines() or [""]:
        if not paragraph:
            lines.append(_row())
            continue
        wrapped = textwrap.wrap(
            paragraph,
            width=BOX_WIDTH - 2,
            replace_whitespace=False,
            drop_whitespace=True,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        lines.extend(_row(part) for part in wrapped)
    lines.append(_bottom_border())
    return "\n".join(lines) + "\n"


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
