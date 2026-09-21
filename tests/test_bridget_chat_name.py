"""Regression coverage for the interactive Bridget display-name onboarding."""

import importlib.util
import io
import json
import os
from pathlib import Path
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
    assert "Välkommen" in rendered
    assert "Vad heter du?" in rendered
    assert rendered.startswith("╭")
    assert "\r│ » Calzone" in rendered
    assert rendered.endswith("╰" + "─" * 62 + "╯\n")
    assert all(len(row) == 64 for row in rendered.splitlines()[:5])


def test_empty_name_reprompts_without_eating_turn():
    out = io.StringIO()
    stream = io.StringIO("  \nAnna\nhello Bridget\n")
    assert naming.prompt_chat_name(stream, out, interactive=True, read_line=read_line) == "Anna"
    assert stream.readline() == "hello Bridget\n"
    assert "Skriv ett namn" in out.getvalue()
    assert out.getvalue().count("│ » ") == 4


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
    assert naming.chat_prompt_label("Calzone", interactive=True, quiet=False) == "\n👤 Calzone: "
    assert naming.chat_prompt_label("Anna", interactive=True, quiet=True) == "\nAnna: "
    assert naming.chat_prompt_label("master", interactive=False, quiet=False) == "\n👹 master: "
    assert naming.chat_prompt_label("master", interactive=False, quiet=True) == "\nmaster: "


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
    assert naming._terminal_width(result) <= 58
    assert naming._terminal_width(naming._entry_row(result)) == 64


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
            if b"\x1b[2A" in found:
                break
        assert b"\x1b[2A" in found
        os.write(master, "Calzoen\x7f\x7fne\n".encode("utf-8"))
        thread.join(3)
        assert not thread.is_alive()
        assert not errors
        assert result == ["Calzone"]
        while select.select([master], [], [], 0.05)[0]:
            found += os.read(master, 4096)
        assert "│ » Calzone".encode() in found
        assert "╰".encode() in found
        assert termios.tcgetattr(slave) == original
    finally:
        if thread.is_alive():
            os.write(master, b"\x04")
            thread.join(1)
        reader.close()
        writer.close()
        os.close(master)
        os.close(slave)
