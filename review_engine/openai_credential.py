"""The OpenAI key for the mq-mcp process, kept out of its subprocesses (#143).

The key is resolved once — from the process environment, else macOS Keychain
(the same service and account as `scripts/bridget` and mq-agent) — and held
here. `scrub_process_env` then removes it from os.environ, so a subprocess
started anywhere in the server inherits no key unless its caller builds the
child environment with `child_env(openai_key=True)`.

Nothing in this module prints or logs the key.
"""
from __future__ import annotations

import os
import subprocess
import sys

ENV_VAR = "OPENAI_API_KEY"
DEFAULT_KEYCHAIN_SERVICE = "mq-openai-api-key"
_PROBE_TIMEOUT = 5

#: Set by scrub_process_env; until then the environment is read on each call.
_held: str | None = None


def _from_keychain() -> str:
    if sys.platform != "darwin":
        return ""
    security = os.environ.get("MQ_SECURITY_BIN", "/usr/bin/security")
    service = os.environ.get("MQ_OPENAI_KEYCHAIN_SERVICE", DEFAULT_KEYCHAIN_SERVICE)
    account = os.environ.get("MQ_OPENAI_KEYCHAIN_ACCOUNT") or os.environ.get("USER", "")
    try:
        result = subprocess.run(
            [security, "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
            check=False,
            env=child_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def openai_api_key() -> str:
    """The key, or "" when neither the environment nor Keychain has one."""
    if _held is not None:
        return _held
    return os.environ.get(ENV_VAR, "").strip() or _from_keychain()


def scrub_process_env() -> bool:
    """Hold the key in this module and remove it from os.environ.

    Returns whether a key is held. Called once when the server starts.
    """
    global _held
    _held = openai_api_key()
    os.environ.pop(ENV_VAR, None)
    return bool(_held)


def child_env(*, openai_key: bool = False) -> dict[str, str]:
    """An environment for a subprocess: os.environ without the key, plus the
    key only when the caller says the child needs it."""
    env = {k: v for k, v in os.environ.items() if k != ENV_VAR}
    if openai_key:
        key = openai_api_key()
        if key:
            env[ENV_VAR] = key
    return env


def _reset_for_tests() -> None:
    global _held
    _held = None
