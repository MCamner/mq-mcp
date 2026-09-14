"""Which repo-signal binary the review engine shells out to.

_resolve_repo_signal_bin decides what _run_repo_signal executes as a
subprocess. It was untested: an earlier branch carried a test for it, but that
test asserted a ~/.local/bin lookup this implementation does not do, so it
codified behaviour main deliberately lacks rather than covering what main has.

The order matters operationally. An explicit REPO_SIGNAL_BIN has to win, or an
operator cannot point the runtime at a specific build; the sibling checkout has
to come next, or the common local setup silently falls through to PATH; and the
bare name has to remain the last resort, or a missing checkout becomes a crash
instead of a FileNotFoundError that _run_repo_signal already documents.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_repo_signal_bin", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sibling_checkout(home: Path) -> Path:
    """The layout the resolver looks for: ~/repo-signal/.venv/bin/repo-signal."""
    executable = home / "repo-signal" / ".venv" / "bin" / "repo-signal"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    return executable


def test_an_explicit_env_override_wins(monkeypatch, tmp_path):
    """An operator pointing at a specific build must not be second-guessed."""
    _sibling_checkout(tmp_path)
    monkeypatch.setenv("REPO_SIGNAL_BIN", "/opt/custom/repo-signal")
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    assert _mod._resolve_repo_signal_bin() == "/opt/custom/repo-signal"


def test_an_empty_env_override_is_not_an_override(monkeypatch, tmp_path):
    """REPO_SIGNAL_BIN="" is an unset variable, not a request to run "" ."""
    executable = _sibling_checkout(tmp_path)
    monkeypatch.setenv("REPO_SIGNAL_BIN", "")
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    assert _mod._resolve_repo_signal_bin() == str(executable)


def test_the_sibling_checkout_is_preferred_over_path(monkeypatch, tmp_path):
    executable = _sibling_checkout(tmp_path)
    monkeypatch.delenv("REPO_SIGNAL_BIN", raising=False)
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    assert _mod._resolve_repo_signal_bin() == str(executable)


def test_without_a_checkout_it_falls_back_to_the_bare_name(monkeypatch, tmp_path):
    """PATH lookup is the last resort, so a missing checkout is not a crash.

    _run_repo_signal documents FileNotFoundError when repo-signal is not
    installed; returning a bare name is what lets subprocess raise that
    rather than the resolver failing first.
    """
    monkeypatch.delenv("REPO_SIGNAL_BIN", raising=False)
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    assert _mod._resolve_repo_signal_bin() == "repo-signal"


def test_a_directory_at_the_candidate_path_is_not_treated_as_the_binary(monkeypatch, tmp_path):
    """exists() is true for a directory too. Only a file can be executed."""
    (tmp_path / "repo-signal" / ".venv" / "bin" / "repo-signal").mkdir(parents=True)
    monkeypatch.delenv("REPO_SIGNAL_BIN", raising=False)
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    assert _mod._resolve_repo_signal_bin() == "repo-signal"


def test_the_resolver_runs_nothing(monkeypatch, tmp_path):
    """Resolution is a lookup. The subprocess belongs to _run_repo_signal."""
    import subprocess

    def _forbidden(*args, **kwargs):
        raise AssertionError("_resolve_repo_signal_bin must not execute anything")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.delenv("REPO_SIGNAL_BIN", raising=False)
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    _mod._resolve_repo_signal_bin()
