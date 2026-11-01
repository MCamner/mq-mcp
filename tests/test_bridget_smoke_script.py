"""scripts/check-bridget-smoke.sh: model-backed Bridget smoke checks.

Locks four things: a missing key is a SKIP (exit 2), never an OK; a failing
Bridget run is a FAIL; the secret is never read into the script or printed;
and smoke runs never touch the operator's ~/.mq history.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-bridget-smoke.sh"
FAKE_KEY = "fake-openai-key-do-not-print-0123456789"


def _fake(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _run(tmp_path, *, key=None, keychain_rc=44, bridget_rc=0):
    log = tmp_path / "calls.log"
    security = _fake(tmp_path / "security", f'echo "security $*" >> "{log}"\nexit {keychain_rc}\n')
    bridget = _fake(
        tmp_path / "bridget",
        f'echo "bridget $* ctx=$MQ_BRIDGET_CONTEXT_DIR home=$MQ_MCP_HOME" >> "{log}"\n'
        'cat >/dev/null\n'
        'echo "Summary of the README."\n'
        'echo "Hej då"\n'
        f"exit {bridget_rc}\n",
    )
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    env.update(MQ_SECURITY_BIN=str(security), MQ_BRIDGET_BIN=str(bridget))
    if key:
        env["OPENAI_API_KEY"] = key
    proc = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    return proc, calls


def test_no_key_anywhere_is_skip_not_ok(tmp_path):
    proc, calls = _run(tmp_path)
    assert proc.returncode == 2
    assert "SKIP:" in proc.stdout
    assert "OK:" not in proc.stdout
    assert "bridget " not in calls


def test_keychain_key_runs_both_smokes_isolated(tmp_path):
    proc, calls = _run(tmp_path, keychain_rc=0)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("OK:") == 2
    bridget_calls = [c for c in calls.splitlines() if c.startswith("bridget ")]
    assert len(bridget_calls) == 2
    home_mq = str(Path.home() / ".mq")
    for call in bridget_calls:
        assert f"home={ROOT}" in call
        assert "ctx=" in call and f"ctx={home_mq}" not in call and "ctx= " not in call


def test_keychain_probe_never_reads_the_secret(tmp_path):
    _, calls = _run(tmp_path, keychain_rc=0)
    probes = [c for c in calls.splitlines() if c.startswith("security ")]
    assert probes
    assert all(" -w" not in p for p in probes)


def test_failing_bridget_is_fail(tmp_path):
    proc, _ = _run(tmp_path, keychain_rc=0, bridget_rc=1)
    assert proc.returncode == 1
    assert "FAIL:" in proc.stderr


def test_env_key_is_used_and_never_printed(tmp_path):
    proc, calls = _run(tmp_path, key=FAKE_KEY)
    assert proc.returncode == 0, proc.stderr
    assert FAKE_KEY not in proc.stdout + proc.stderr + calls


def test_validate_counts_smoke_skips():
    script = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")
    assert "check-bridget-smoke.sh" in script
    assert "SKIPPED" in script
