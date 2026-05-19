import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import bridget_voice


def test_voice_toggle_state_file(monkeypatch, tmp_path):
    state = tmp_path / "voice_state"
    voice = tmp_path / "voice_name"
    monkeypatch.setenv("BRIDGET_VOICE_STATE_FILE", str(state))
    monkeypatch.setenv("BRIDGET_VOICE_NAME_FILE", str(voice))
    monkeypatch.delenv("BRIDGET_VOICE_ENABLED", raising=False)

    bridget_voice.set_voice_enabled(True)
    assert bridget_voice.is_voice_enabled() is True

    bridget_voice.set_voice_enabled(False)
    assert bridget_voice.is_voice_enabled() is False


def test_voice_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGET_VOICE_STATE_FILE", str(tmp_path / "voice_state"))

    monkeypatch.setenv("BRIDGET_VOICE_ENABLED", "1")
    assert bridget_voice.is_voice_enabled() is True

    monkeypatch.setenv("BRIDGET_VOICE_ENABLED", "0")
    assert bridget_voice.is_voice_enabled() is False


def test_voice_name_file(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGET_VOICE_STATE_FILE", str(tmp_path / "voice_state"))
    monkeypatch.setenv("BRIDGET_VOICE_NAME_FILE", str(tmp_path / "voice_name"))
    monkeypatch.delenv("BRIDGET_VOICE_NAME", raising=False)

    bridget_voice.set_voice_name("Samantha")
    assert bridget_voice.get_voice_name() == "Samantha"


def test_strip_for_speech_removes_code_blocks():
    text = """
    Here is code:

    ```bash
    rm -rf something
    ```

    MCP tool safety looks good.
    """
    spoken = bridget_voice.strip_for_speech(text)
    assert "rm -rf" not in spoken
    assert "M C P" in spoken


def test_strip_for_speech_truncates():
    long_text = "word " * 300
    spoken = bridget_voice.strip_for_speech(long_text)
    assert len(spoken) <= 705  # MAX_SPEECH_CHARS + "." with some rstrip slack


def test_handle_voice_command_on_off(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGET_VOICE_STATE_FILE", str(tmp_path / "voice_state"))
    monkeypatch.setenv("BRIDGET_VOICE_NAME_FILE", str(tmp_path / "voice_name"))
    monkeypatch.delenv("BRIDGET_VOICE_ENABLED", raising=False)

    assert bridget_voice.handle_voice_command("--voice-on") is True
    assert bridget_voice.is_voice_enabled() is True

    assert bridget_voice.handle_voice_command("--voice-off") is True
    assert bridget_voice.is_voice_enabled() is False

    assert bridget_voice.handle_voice_command("vanlig fråga") is False


def test_handle_voice_name_command(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGET_VOICE_STATE_FILE", str(tmp_path / "voice_state"))
    monkeypatch.setenv("BRIDGET_VOICE_NAME_FILE", str(tmp_path / "voice_name"))
    monkeypatch.delenv("BRIDGET_VOICE_NAME", raising=False)

    assert bridget_voice.handle_voice_command("--voice-name Alva") is True
    assert bridget_voice.get_voice_name() == "Alva"
