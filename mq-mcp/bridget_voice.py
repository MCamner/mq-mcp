from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


_DEFAULT_VOICE = "Alva"
_MAX_SPEECH_CHARS = int(os.getenv("BRIDGET_VOICE_MAX_CHARS", "700"))


def _state_file() -> Path:
    return Path(
        os.getenv(
            "BRIDGET_VOICE_STATE_FILE",
            str(Path.home() / ".mq-mcp" / "bridget_voice_enabled"),
        )
    ).expanduser()


def _voice_file() -> Path:
    return Path(
        os.getenv(
            "BRIDGET_VOICE_NAME_FILE",
            str(Path.home() / ".mq-mcp" / "bridget_voice_name"),
        )
    ).expanduser()


def set_voice_enabled(enabled: bool) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("on\n" if enabled else "off\n", encoding="utf-8")


def is_voice_enabled() -> bool:
    override = os.getenv("BRIDGET_VOICE_ENABLED", "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    path = _state_file()
    if not path.exists():
        return False
    return path.read_text(encoding="utf-8", errors="replace").strip().lower() == "on"


def set_voice_name(name: str) -> None:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Voice name cannot be empty.")
    path = _voice_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned + "\n", encoding="utf-8")


def get_voice_name() -> str:
    env_voice = os.getenv("BRIDGET_VOICE_NAME", "").strip()
    if env_voice:
        return env_voice
    path = _voice_file()
    if path.exists():
        value = path.read_text(encoding="utf-8", errors="replace").strip()
        if value:
            return value
    return _DEFAULT_VOICE


def strip_for_speech(text: str) -> str:
    """Strip markdown/terminal formatting to produce a clean spoken summary."""
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", " link ", cleaned)
    cleaned = re.sub(r"[-*_#>|]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    for old, new in {
        "MCP": "M C P",
        "API": "A P I",
        "JSON": "J SON",
        "CLI": "C L I",
        "repo": "repository",
    }.items():
        cleaned = cleaned.replace(old, new)

    if len(cleaned) > _MAX_SPEECH_CHARS:
        cleaned = cleaned[:_MAX_SPEECH_CHARS].rstrip() + "."

    return cleaned


def speak_if_enabled(text: str) -> None:
    if not is_voice_enabled():
        return
    if not shutil.which("say"):
        return
    speech = strip_for_speech(text)
    if not speech:
        return
    try:
        subprocess.Popen(
            ["say", "-v", get_voice_name(), speech],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return


def handle_voice_command(prompt: str) -> bool:
    p = " ".join(prompt.strip().lower().split())

    if p in {"--voice-on", "voice on", "röst på", "slå på röst"}:
        set_voice_enabled(True)
        print("BRIDGET voice: on")
        return True

    if p in {"--voice-off", "voice off", "röst av", "slå av röst"}:
        set_voice_enabled(False)
        print("BRIDGET voice: off")
        return True

    if p in {"--voice-status", "voice status", "röst status"}:
        state_path = _state_file()
        print(f"BRIDGET voice: {'on' if is_voice_enabled() else 'off'}")
        print(f"Voice name:    {get_voice_name()}")
        print(f"State file:    {state_path}")
        return True

    if p in {"--voice-test", "voice test", "testa röst"}:
        print(f"Testing Bridget voice: {get_voice_name()}")
        was_enabled = is_voice_enabled()
        set_voice_enabled(True)
        speak_if_enabled("Hej Calzone. Bridget är online.")
        set_voice_enabled(was_enabled)
        return True

    if p in {"--voice-list", "voice list", "lista röster"}:
        if shutil.which("say"):
            subprocess.run(["say", "-v", "?"], check=False)
        else:
            print("say command not found.")
        return True

    if p.startswith("--voice-name "):
        name = prompt.strip()[len("--voice-name "):].strip()
        set_voice_name(name)
        print(f"BRIDGET voice name set to: {name}")
        return True

    return False
