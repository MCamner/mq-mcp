"""Regression coverage for the interactive Bridget display-name onboarding."""

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import select
import threading

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "mq-mcp" / "bridget_chat_name.py"
if not MODULE_PATH.is_file():
    MODULE_PATH = Path(__file__).resolve().with_name("bridget_chat_name_v2.py")
SPEC = importlib.util.spec_from_file_location("bridget_chat_name_test_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
naming = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(naming)


@pytest.fixture(autouse=True)
def fixed_terminal_width(monkeypatch):
    """Box width follows the terminal; pin it so assertions are stable."""
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


def read_line(stream, out):
    line = stream.readline()
    return None if line == "" else line.strip()


def test_welcome_box_and_custom_name():
    out = io.StringIO()
    name = naming.prompt_chat_name(
        io.StringIO("Calzone\n"), out, interactive=True, read_line=read_line
    )
    assert name == "Calzone"
    rendered = out.getvalue()
    rows = rendered.replace("\r", "\n").splitlines()
    assert rendered.startswith("╭─ ◉‿◉ Bridget ─")
    assert "Hej. Vem pratar jag med?" in rendered
    assert any(row.startswith("│  › Calzone ") and row.endswith(" 7/32 │") for row in rows)
    assert rows[-1].startswith("╰─ ↵ fortsätt · ctrl-c avbryt ─")
    assert rows[-1].endswith("─╯")
    assert all(len(row) == 74 for row in rows if row.startswith(("╭", "│", "╰")) and not row.endswith("› "))
    assert "\x1b" not in rendered  # test streams are not terminals: no colour


def test_welcome_box_matches_session_card_width(monkeypatch):
    """The welcome frame and the Bridget card share one outer width."""
    monkeypatch.setenv("COLUMNS", "60")
    out = io.StringIO()
    naming.prompt_chat_name(io.StringIO("Anna\n"), out, interactive=True, read_line=read_line)
    assert all(len(row) == 58 for row in out.getvalue().splitlines()[:4])


def test_empty_name_reprompts_without_eating_turn():
    out = io.StringIO()
    stream = io.StringIO("  \nAnna\nhello Bridget\n")
    assert naming.prompt_chat_name(stream, out, interactive=True, read_line=read_line) == "Anna"
    assert stream.readline() == "hello Bridget\n"
    assert "Skriv ett namn" in out.getvalue()
    assert out.getvalue().count("│  › ") == 4


def test_noninteractive_does_not_consume_piped_chat():
    out = io.StringIO()
    stream = io.StringIO("first question\nexit\n")

    def fail_read(*_args):
        raise AssertionError("piped input must remain untouched")

    assert naming.prompt_chat_name(stream, out, interactive=False, read_line=fail_read) == "master"
    assert stream.readline() == "first question\n"
    assert out.getvalue() == ""


def test_eof_ends_onboarding_without_starting_chat():
    assert naming.prompt_chat_name(
        io.StringIO(""), io.StringIO(), interactive=True, read_line=read_line
    ) is None


def test_chat_label_uses_name_and_preserves_piped_mode():
    assert naming.chat_prompt_label("Calzone", interactive=True, quiet=False) == "\n› Calzone: "
    assert naming.chat_prompt_label("Anna", interactive=True, quiet=True) == "\nAnna: "
    assert naming.chat_prompt_label("master", interactive=False, quiet=False) == "\n▙█▟ master: "
    assert naming.chat_prompt_label("master", interactive=False, quiet=True) == "\nmaster: "


def test_chat_label_colors_only_the_sprite_and_only_on_a_terminal():
    """Green marks the operator, but never leaks into captured output.

    The launcher captures Bridget's stdout, so a colour escape must be gated
    on the *output* stream being a terminal, exactly like the scramble
    animation. Only the sprite is coloured; the name stays the terminal's
    default so an operator name can never be mistaken for Bridget's voice.
    """
    green, reset = "\x1b[32m", "\x1b[0m"

    assert naming.chat_prompt_label(
        "Calzone", interactive=True, quiet=False, color=True
    ) == "\n\x1b[38;2;132;191;196m› Calzone\x1b[0m: "
    assert naming.chat_prompt_label(
        "master", interactive=False, quiet=False, color=True
    ) == f"\n{green}▙█▟{reset} master: "

    # Not a terminal: byte-identical to the uncoloured label.
    assert naming.chat_prompt_label(
        "Calzone", interactive=True, quiet=False, color=False
    ) == "\n› Calzone: "
    # --quiet still wins over colour.
    assert naming.chat_prompt_label(
        "Calzone", interactive=True, quiet=True, color=True
    ) == "\nCalzone: "


def test_name_is_session_data_in_model_context():
    name = 'Anna "A"'
    context = naming.chat_identity_context(name)
    assert json.dumps(name, ensure_ascii=False) in context
    assert "untrusted data" in context
    assert "instead of a default nickname" in context


def test_control_characters_and_ansi_codes_removed():
    raw = "A\x1b[31m\x00" + "X" * 60
    result = naming.prompt_chat_name(
        io.StringIO(raw + "\n"), io.StringIO(), interactive=True, read_line=read_line
    )
    assert result is not None
    assert len(result) <= 32
    assert all(char.isprintable() for char in result)
    assert "\x1b" not in result
    assert "[31m" not in result


def test_unicode_name_preserved():
    assert naming.prompt_chat_name(
        io.StringIO("  Åsa Öberg  \n"), io.StringIO(), interactive=True, read_line=read_line
    ) == "Åsa Öberg"


def test_wide_characters_fit_inside_frame():
    result = naming.prompt_chat_name(
        io.StringIO("界" * 40 + "\n"), io.StringIO(), interactive=True, read_line=read_line
    )
    assert result is not None
    assert naming._terminal_width(result) <= 72 - 13
    assert naming._terminal_width(naming._entry_row(result)) == 74
    assert naming._terminal_width(naming._entry_row(result, cursor=True)) == 74


@pytest.mark.skipif(os.name != "posix", reason="requires a POSIX terminal")
def test_real_tty_typing_stays_within_box_and_restores_terminal():
    import pty
    import termios

    master, slave = pty.openpty()
    reader = os.fdopen(os.dup(slave), "r", encoding="utf-8", buffering=1)
    writer = os.fdopen(os.dup(slave), "w", encoding="utf-8", buffering=1)
    original = termios.tcgetattr(slave)
    result = []
    errors = []

    def run():
        try:
            result.append(naming.prompt_chat_name(
                reader, writer, interactive=True, read_line=read_line
            ))
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    try:
        thread.start()
        found = b""
        # Wait for the cursor-positioning sequence, which is emitted after
        # the welcome box is fully drawn and the name input row is selected.
        for _ in range(30):
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                found += os.read(master, 4096)
            if b"\x1b[3A" in found:
                break
        assert b"\x1b[3A" in found
        assert found.startswith(b"\x1b[?25l")  # real cursor hidden while typing
        assert "skriv ditt namn".encode() in found
        os.write(master, "Calzoen\x7f\x7fne\n".encode("utf-8"))
        thread.join(3)
        assert not thread.is_alive()
        assert not errors
        assert result == ["Calzone"]
        while select.select([master], [], [], 0.05)[0]:
            found += os.read(master, 4096)
        plain = re.sub(rb"\x1b\[[0-9;]*m", b"", found)
        assert "› Calzone█".encode() in plain
        assert "╰─ ".encode() in plain
        # The frame is erased so the session card can take its place,
        # and the terminal cursor is shown again.
        assert found.endswith(b"\r\x1b[4A\x1b[J\x1b[?25h")
        restored = termios.tcgetattr(slave)
        # BSD/macOS may set PENDIN while returning from cbreak to canonical
        # input when bytes were queued on the pseudo-terminal. PENDIN is
        # kernel-maintained pending-input state, not a mode chosen by Bridget;
        # compare every stable terminal setting while ignoring only that bit.
        transient = getattr(termios, "PENDIN", 0)
        restored[3] &= ~transient
        original[3] &= ~transient
        assert restored == original
    finally:
        if thread.is_alive():
            os.write(master, b"\x04")
            thread.join(1)
        reader.close()
        writer.close()
        os.close(master)
        os.close(slave)


def test_entry_row_shows_placeholder_only_while_empty():
    empty = naming._entry_row("", cursor=True)
    assert "› █ skriv ditt namn" in empty
    assert empty.endswith(" 0/32 │")
    typed = naming._entry_row("Ada", cursor=True)
    assert "› Ada█" in typed and "skriv ditt namn" not in typed


def test_colour_rows_keep_the_frame_width():
    row = naming._entry_row("Ada", color=True, cursor=True)
    assert "\x1b[" in row
    assert naming._terminal_width(naming._ANSI_ESCAPE.sub("", row)) == 74
    assert len(naming._ANSI_ESCAPE.sub("", naming._title_border(True))) == 74


@pytest.mark.skipif(os.name != "posix", reason="requires a POSIX terminal")
def test_ctrl_c_cancels_name_entry_as_a_key():
    """Ctrl-C must reach the reader as a byte, not as SIGINT.

    Under asyncio, SIGINT only schedules a task cancellation while the blocking
    read restarts, so the operator was stuck at the prompt. With ISIG off, the
    reader sees 0x03 and cancels; the cursor is shown again.
    """
    import pty
    import termios

    master, slave = pty.openpty()
    reader = os.fdopen(os.dup(slave), "r", encoding="utf-8", buffering=1)
    writer = os.fdopen(os.dup(slave), "w", encoding="utf-8", buffering=1)
    original = termios.tcgetattr(slave)
    result = []

    def run():
        result.append(naming.prompt_chat_name(reader, writer, interactive=True, read_line=read_line))

    thread = threading.Thread(target=run)
    try:
        thread.start()
        found = b""
        for _ in range(30):
            if select.select([master], [], [], 0.1)[0]:
                found += os.read(master, 4096)
            if b"\x1b[3A" in found:
                break
        # Wait until the reader has echoed a key: only then is ISIG off.
        os.write(master, b"Ada")
        for _ in range(30):
            if select.select([master], [], [], 0.1)[0]:
                found += os.read(master, 4096)
            if "Ada█".encode() in found:
                break
        os.write(master, b"\x03")
        thread.join(3)
        assert not thread.is_alive()
        assert result == [None]
        while select.select([master], [], [], 0.05)[0]:
            found += os.read(master, 4096)
        assert found.endswith(b"\x1b[3B\r\x1b[?25h")
        restored = termios.tcgetattr(slave)
        transient = getattr(termios, "PENDIN", 0)
        restored[3] &= ~transient
        original[3] &= ~transient
        assert restored == original
    finally:
        if thread.is_alive():
            os.write(master, b"\x04")
            thread.join(1)
        reader.close()
        writer.close()
        os.close(master)
        os.close(slave)
