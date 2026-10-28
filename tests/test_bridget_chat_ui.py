import importlib.util
import re
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "mq-mcp" / "bridget_chat_ui.py"
SPEC = importlib.util.spec_from_file_location("bridget_chat_ui_test_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui)

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def assert_box_width(card: str, width: int = 64) -> None:
    for line in card.splitlines():
        assert ui.terminal_width(line) == width


def test_session_card_contains_live_identity_and_runtime_state():
    card = ui.render_session_card(
        "Calzone", model="gpt-5.4-mini", tool_count=130,
        project="mq-agent", branch="main",
    )
    assert "Hej Calzone." in card
    assert "MCP ansluten" in card
    assert "130 verktyg" in card
    assert "mq-agent/main" in card
    assert "/help" in card
    assert all(ui.terminal_width(line) <= 74 for line in card.splitlines())


def test_dynamic_values_cannot_inject_ansi_or_new_rows():
    card = ui.render_session_card(
        "A\x1b[31m\nINJECT", model="model\nBAD", tool_count=1,
        project="repo\x1b[2J", branch="main",
    )
    assert "\x1b[31m" not in card
    assert "\x1b[2J" not in card
    assert "A INJECT" in card
    assert "model BAD" in card
    assert all(ui.terminal_width(line) <= 74 for line in card.splitlines())


def test_color_is_opt_in_and_does_not_change_card_width():
    plain = ui.render_session_card("Åsa", model="gpt", tool_count=2)
    colored = ui.render_session_card("Åsa", model="gpt", tool_count=2, color=True)
    assert "\x1b[" not in plain
    assert "\x1b[" in colored
    assert all(ui.terminal_width(line) <= 74 for line in colored.splitlines())


def test_hud_clamps_context_and_truncates_long_repo():
    hud = ui.render_hud(
        project="x" * 100, branch="main", tool_count=130,
        context_percent=122,
    )
    assert "100%" in hud
    assert all(ui.terminal_width(line) <= 74 for line in hud.splitlines())


def test_response_card_wraps_long_and_wide_text():
    card = ui.render_response_card("界" * 80 + " ordinary words " * 10)
    assert "Bridget" in card
    assert len(card.splitlines()) > 4
    assert all(ui.terminal_width(line) <= 74 for line in card.splitlines())


def test_tool_summary_is_compact_and_bounded_to_three_names():
    summary = ui.render_tool_summary(["git_status", "read_file", "search", "fourth"])
    assert summary == "    Anrop: git_status, read_file, search +1\n"


def test_help_card_lists_local_commands():
    card = ui.render_help_card()
    for command in ("/status", "/clear", "/face", "/help", "/exit"):
        assert command in card
    assert all(ui.terminal_width(line) <= 74 for line in card.splitlines())


def test_thinking_frame_and_clear_sequence_are_explicit_ansi_only():
    assert ui.thinking_frame("⠋") == "\r◉_◉ Bridget tänker ⠋"
    assert ANSI.search(ui.thinking_frame("⠋", color=True))
    assert ui.clear_screen_sequence() == "\x1b[2J\x1b[H"


def test_console_header_is_compact():
    card = ui.render_session_card("mongo", model="gpt", tool_count=136, project="mq-mcp")
    assert "◉‿◉ Bridget" in card
    assert "MCP ansluten" in card
    assert len(card.splitlines()) <= 5


def test_console_response_is_open_and_preserves_wide_text():
    answer = "界" * 80 + "\n    indented code"
    card = ui.render_response_card(answer)
    assert "◉‿◉ Bridget" in card
    assert "╭" not in card and "│" not in card
    assert card.count("界") == 80
    assert "    indented code" in card
    assert all(ui.terminal_width(line) <= 74 for line in card.splitlines())


def test_status_strip_shows_model_and_context_bar():
    hud = ui.render_hud(project="mq-mcp", branch=None, tool_count=136,
                        context_percent=33, model="gpt-5.4-mini")
    assert "gpt-5.4-mini" in hud and "33%" in hud
    assert "▰" in hud and "/help" in hud
    assert "╭" not in hud


def test_tool_activity_distinguishes_failures():
    assert "klart" in ui.render_tool_activity("git_status")
    failed = ui.render_tool_activity("shell_exec", failed=True)
    assert "misslyckades" in failed
    assert "✓" not in failed


def test_console_adapts_to_narrow_terminal_without_losing_response(monkeypatch):
    import os
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback: os.terminal_size((40, 24)))
    card = ui.render_session_card("mongo", model="gpt", tool_count=136, project="mq-mcp")
    hud = ui.render_hud(project="mq-mcp", branch=None, tool_count=136, context_percent=33)
    response = ui.render_response_card("界" * 80)
    assert response.count("界") == 80
    for text in (card, hud, response, ui.render_tool_running("x" * 100),
                 ui.render_tool_activity("x" * 100, failed=True)):
        assert all(ui.terminal_width(line) <= 38 for line in text.splitlines())


def test_activity_sanitizes_tool_names():
    for text in (ui.render_tool_running("evil\x1b[2J\nname"),
                 ui.render_tool_activity("evil\x1b[2J\nname")):
        assert "\x1b" not in text
        assert "evil name" in text
