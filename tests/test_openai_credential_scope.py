"""#143: the OpenAI key stays in the mq-mcp process and reaches only the
children that need it.

The server resolves the key once (env, then Keychain), removes it from
os.environ, and hands it to a subprocess only where a tool opts in. No real
key or Keychain is used; values here are fakes.
"""

import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
FAKE_CRED = "fake-cred-value-not-real-4Kd9"

from review_engine import openai_credential as cred  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_cache():
    cred._reset_for_tests()
    yield
    cred._reset_for_tests()


def _fake_security(tmp_path, value, rc=0):
    log = tmp_path / "security.log"
    path = tmp_path / "security"
    path.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> "{log}"\n'
        f'[ {rc} -eq 0 ] && printf "%s\\n" "{value}"\n'
        f"exit {rc}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path, log


# --- resolution ---------------------------------------------------------------


def test_env_value_wins(monkeypatch, tmp_path):
    security, log = _fake_security(tmp_path, "from-keychain")
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_CRED)
    monkeypatch.setenv("MQ_SECURITY_BIN", str(security))
    assert cred.openai_api_key() == FAKE_CRED
    assert not log.exists()


def test_keychain_fallback(monkeypatch, tmp_path):
    security, log = _fake_security(tmp_path, FAKE_CRED)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MQ_SECURITY_BIN", str(security))
    monkeypatch.setattr(cred.sys, "platform", "darwin")
    assert cred.openai_api_key() == FAKE_CRED
    assert "-s mq-openai-api-key" in log.read_text()


def test_missing_everywhere_is_empty(monkeypatch, tmp_path):
    security, _ = _fake_security(tmp_path, "", rc=44)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MQ_SECURITY_BIN", str(security))
    monkeypatch.setattr(cred.sys, "platform", "darwin")
    assert cred.openai_api_key() == ""


# --- scrub and child env ------------------------------------------------------


def test_scrub_removes_key_but_keeps_it_in_process(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_CRED)
    assert cred.scrub_process_env() is True
    assert "OPENAI_API_KEY" not in os.environ
    assert cred.openai_api_key() == FAKE_CRED


def test_child_env_excludes_key_unless_asked(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_CRED)
    monkeypatch.setenv("MQ_KEEP_ME", "1")
    cred.scrub_process_env()
    plain = cred.child_env()
    assert "OPENAI_API_KEY" not in plain
    assert plain["MQ_KEEP_ME"] == "1"
    assert cred.child_env(openai_key=True)["OPENAI_API_KEY"] == FAKE_CRED


def test_child_env_drops_a_key_even_if_env_still_has_one(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_CRED)  # not scrubbed
    assert "OPENAI_API_KEY" not in cred.child_env()


# --- server wiring ------------------------------------------------------------


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_CRED)
    spec = importlib.util.spec_from_file_location("mq_mcp_server_cred_scope", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cred.scrub_process_env()
    return mod


def _capture(calls, stdout=""):
    def run(cmd, **kwargs):
        env = kwargs.get("env")
        calls.append(dict(os.environ) if env is None else dict(env))
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
    return run


def test_diagnostic_subprocess_gets_no_key(server, monkeypatch):
    calls: list = []
    monkeypatch.setattr(server.subprocess, "run", _capture(calls))
    server.run_mqlaunch_doctor()
    assert calls and "OPENAI_API_KEY" not in calls[0]


def test_mqlaunch_ask_gets_the_key(server, monkeypatch):
    calls: list = []
    monkeypatch.setattr(server.subprocess, "run", _capture(calls, stdout="answer"))
    server.run_mqlaunch_ask("what is mq-mcp?")
    assert calls and calls[0].get("OPENAI_API_KEY") == FAKE_CRED


@pytest.mark.parametrize("mode,expected", [("local-fast", False), ("cloud-verify", True)])
def test_image_analyze_gets_the_key_only_for_cloud(server, monkeypatch, tmp_path, mode, expected):
    image = tmp_path / "x.png"
    image.write_bytes(b"\x89PNG")
    calls: list = []
    monkeypatch.setattr(server, "resolve_allowed_local_file", lambda p: Path(p))
    monkeypatch.setattr(server.subprocess, "run", _capture(calls, stdout="{}"))
    server.image_analyze(str(image), mode=mode)
    assert calls and ("OPENAI_API_KEY" in calls[0]) is expected


def test_redacted_env_still_reports_the_key_as_set(server):
    entry = server._redacted_env()["OPENAI_API_KEY"]
    assert entry == {"set": True, "value": "<redacted>"}


# --- guards against regressions -----------------------------------------------


def test_opt_in_list_is_exactly_known():
    text = SERVER_PATH.read_text(encoding="utf-8")
    opted = set()
    current = None
    for line in text.splitlines():
        m = re.match(r"def (\w+)\(", line)
        if m:
            current = m.group(1)
        passthrough = "openai_key=openai_key" in line
        if "openai_key=" in line and not passthrough and not line.lstrip().startswith(("def ", "#")):
            opted.add(current)
    assert opted == {"run_mqlaunch_ask", "image_analyze"}


def test_no_direct_key_reads_outside_the_credential_module():
    pattern = re.compile(r"""os\.(getenv|environ\.get)\(\s*["']OPENAI_API_KEY|os\.environ\[\s*["']OPENAI_API_KEY""")
    offenders = []
    for path in [SERVER_PATH, *sorted((ROOT / "review_engine").glob("*.py"))]:
        if path.name == "openai_credential.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{n}")
    assert offenders == []


def test_server_scrubs_before_it_serves():
    text = SERVER_PATH.read_text(encoding="utf-8")
    main = text[text.index('if __name__ == "__main__":'):]
    assert main.index("scrub_process_env()") < main.index("mcp.run(")
