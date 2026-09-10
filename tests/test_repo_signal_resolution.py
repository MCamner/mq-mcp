import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_repo_signal", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_resolve_repo_signal_bin_finds_user_local_install(monkeypatch, tmp_path):
    executable = tmp_path / ".local" / "bin" / "repo-signal"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.delenv("REPO_SIGNAL_BIN", raising=False)
    monkeypatch.setattr(_mod.Path, "home", lambda: tmp_path)

    assert _mod._resolve_repo_signal_bin() == str(executable)
