"""End-to-end: what the model says versus what the operator is shown.

The model output in these tests is copied from the real `review_repo` run
against `mq-mcp/release_gate/` — the one that reported a missing module
docstring in a file that opens with one, asked for return annotations already
present, and put every finding on the wrong line.

No OpenAI call is made: the client is replaced with one that returns that exact
text, so the assertions are about the pipeline around the model, which is the
part that can be made correct.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_verification", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SOURCE = '''"""Deterministic Release Gate v2 checks."""
from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_tests_pass(repo: Path) -> str:
    return "ok"


def genuinely_undocumented(repo):
    return "ok"
'''

# Verbatim shapes from the run that prompted this work.
MODEL_OUTPUT = """[MISSING] checks.py:1
Module has no module-level docstring; add a top-level summary describing the purpose and scope of this file.

[SUGGESTION] checks.py:34
Add a return type annotation to check_tests_pass function signature to improve type clarity.

[MISSING] checks.py:412
Public function genuinely_undocumented is missing a docstring; add a one-line description.
"""


class _FakeCompletions:
    def __init__(self, text: str, calls: list[str]) -> None:
        self._text = text
        self._calls = calls

    def create(self, **kwargs):
        self._calls.append(kwargs["messages"][1]["content"])

        class _Message:
            content = self._text

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        return _Response()


class _FakeClient:
    def __init__(self, text: str, calls: list[str]) -> None:
        self.chat = type("_Chat", (), {"completions": _FakeCompletions(text, calls)})()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "checks.py").write_text(SOURCE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def fake_openai(monkeypatch):
    calls: list[str] = []

    def _install(text: str):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        # server.py does `import openai as _openai` inside the function, so the
        # substitution has to happen in sys.modules rather than on the module.
        fake_module = type(
            "_FakeOpenAIModule",
            (),
            {"OpenAI": staticmethod(lambda api_key: _FakeClient(text, calls))},
        )
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        return calls

    return _install


def test_refuted_findings_never_reach_the_operator(repo, fake_openai, monkeypatch):
    fake_openai(MODEL_OUTPUT)
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: repo)

    output = _mod.review_file("checks.py", mode="comment", repo_path=str(repo))

    assert "module-level docstring" not in output, output
    assert "return type annotation to check_tests_pass" not in output, output
    # The one real gap survives.
    assert "genuinely_undocumented" in output, output


def test_the_operator_is_told_what_was_dropped(repo, fake_openai, monkeypatch):
    """A silent filter would be its own kind of dishonesty."""
    fake_openai(MODEL_OUTPUT)
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: repo)

    output = _mod.review_file("checks.py", mode="comment", repo_path=str(repo))

    assert "Dropped as contradicted by the file" in output, output
    assert output.count("  - ") == 2, output


def test_the_surviving_finding_points_at_the_real_line(repo, fake_openai, monkeypatch):
    fake_openai(MODEL_OUTPUT)
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: repo)

    output = _mod.review_file("checks.py", mode="comment", repo_path=str(repo))

    expected = SOURCE.splitlines().index("def genuinely_undocumented(repo):") + 1
    assert f"checks.py:{expected}" in output, output
    assert "checks.py:412" not in output, output


def test_the_model_is_given_line_numbers_to_cite(repo, fake_openai, monkeypatch):
    """The drift was the model counting; it should not have to."""
    calls = fake_openai(MODEL_OUTPUT)
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: repo)

    _mod.review_file("checks.py", mode="comment", repo_path=str(repo))

    assert calls, "no request was made"
    prompt = calls[0]
    assert "do not count lines yourself" in prompt
    numbered = SOURCE.splitlines().index("def genuinely_undocumented(repo):") + 1
    assert f"{numbered}\tdef genuinely_undocumented(repo):" in prompt, prompt[-400:]


def test_a_large_file_is_reviewed_in_chunks_instead_of_skipped(
    tmp_path, fake_openai, monkeypatch
):
    """The old behaviour returned 'File too large' and reviewed nothing."""
    padding = "\n".join(
        f"def filler_{i}():\n    return {i}  # padding" for i in range(6000)
    )
    big = f'"""Big module."""\n{padding}\n'
    (tmp_path / "big.py").write_text(big, encoding="utf-8")
    assert len(big.encode()) > 200_000, "fixture is not large enough to matter"

    calls = fake_openai("[NOTE] big.py:1\nNothing of note.\n")
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: tmp_path)

    output = _mod.review_file("big.py", mode="comment", repo_path=str(tmp_path))

    assert "File too large" not in output, output
    assert len(calls) > 1, f"expected several chunk requests, got {len(calls)}"


def test_deep_mode_still_refuses_a_file_it_would_re_read_per_pass(
    tmp_path, fake_openai, monkeypatch
):
    big = '"""Big."""\n' + "\n".join(f"x_{i} = {i}" for i in range(40000))
    (tmp_path / "big.py").write_text(big, encoding="utf-8")
    fake_openai("")
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: tmp_path)

    output = _mod.review_file("big.py", mode="comment", deep=True, repo_path=str(tmp_path))

    assert "too large for deep review" in output.lower(), output
