import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "bridget"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _base_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "mq-mcp-home"
    app = home / "mq-mcp"
    app.mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "child.log"

    _write_executable(
        bin_dir / "uv",
        "#!/usr/bin/env bash\n"
        "printf 'key=%s\\n' \"${OPENAI_API_KEY:-}\" >\"$BRIDGET_TEST_LOG\"\n"
        "printf 'local=%s\\n' \"${MQ_MCP_LOCAL_REPOS:-}\" >>\"$BRIDGET_TEST_LOG\"\n"
        "printf 'arg=%s\\n' \"$@\" >>\"$BRIDGET_TEST_LOG\"\n",
    )

    env = os.environ.copy()
    env["MQ_MCP_HOME"] = str(home)
    env["BRIDGET_TEST_LOG"] = str(log)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env.pop("OPENAI_API_KEY", None)
    return env, app, log


def test_keychain_key_replaces_dotenv_key_without_argv_leak(tmp_path: Path) -> None:
    env, app, log = _base_env(tmp_path)
    app.joinpath(".env").write_text(
        "OPENAI_API_KEY=sk-from-dotenv\nMQ_MCP_LOCAL_REPOS=/tmp/repo-a\n",
        encoding="utf-8",
    )

    secret = "sk-keychain-test-secret"
    security = tmp_path / "security"
    _write_executable(security, f"#!/usr/bin/env bash\nprintf '%s\\n' '{secret}'\n")
    env["MQ_SECURITY_BIN"] = str(security)

    result = subprocess.run(
        [str(LAUNCHER), "--chat"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    child = log.read_text(encoding="utf-8")
    assert f"key={secret}" in child
    assert "key=sk-from-dotenv" not in child
    assert "local=/tmp/repo-a" in child
    assert "arg=--chat" in child
    assert secret not in result.stdout
    assert secret not in result.stderr
    assert not any(secret in line for line in child.splitlines() if line.startswith("arg="))


def test_inherited_process_key_wins_without_keychain_lookup(tmp_path: Path) -> None:
    env, app, log = _base_env(tmp_path)
    app.joinpath(".env").write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")

    security = tmp_path / "security-should-not-run"
    _write_executable(security, "#!/usr/bin/env bash\nexit 99\n")
    env["MQ_SECURITY_BIN"] = str(security)
    env["OPENAI_API_KEY"] = "sk-inherited-process-key"

    subprocess.run([str(LAUNCHER), "--chat"], env=env, check=True)

    child = log.read_text(encoding="utf-8")
    assert "key=sk-inherited-process-key" in child
    assert "key=sk-from-dotenv" not in child


def test_tools_stays_usable_when_keychain_has_no_key(tmp_path: Path) -> None:
    env, _app, log = _base_env(tmp_path)
    security = tmp_path / "security-missing"
    _write_executable(security, "#!/usr/bin/env bash\nexit 44\n")
    env["MQ_SECURITY_BIN"] = str(security)

    result = subprocess.run(
        [str(LAUNCHER), "--tools"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    child = log.read_text(encoding="utf-8")
    assert "key=" in child
    assert "arg=--tools" in child
    assert "OPENAI_API_KEY" not in result.stdout
    assert "OPENAI_API_KEY" not in result.stderr
