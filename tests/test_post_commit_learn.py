import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "post_commit_learn", ROOT / "scripts" / "post_commit_learn.py"
)
pcl = importlib.util.module_from_spec(_spec)
sys.modules["post_commit_learn"] = pcl
_spec.loader.exec_module(pcl)


def _redirect_files(monkeypatch, tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    lessons = tmp_path / "lessons.jsonl"
    monkeypatch.setattr(pcl, "INBOX_FILE", inbox)
    monkeypatch.setattr(pcl, "LESSONS_FILE", lessons)
    monkeypatch.setattr(pcl, "LOG_FILE", tmp_path / "post-commit.log")
    monkeypatch.setattr(pcl, "PENDING_FILE", tmp_path / "pending-commits.txt")
    return inbox, lessons


def test_append_inbox_writes_pending_record(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    pcl.append_inbox(
        {"pattern_name": "p", "summary": "s", "confidence": "high", "evidence": ["e"]},
        "abc123def456",
    )
    rec = json.loads(inbox.read_text().strip())
    assert rec["status"] == "pending"
    assert rec["source"] == "post-commit"
    assert rec["commit"] == "abc123def456"[:12]
    assert rec["confidence"] == "high"


def test_is_duplicate_detects_paraphrase(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    existing = [pcl._words("run git diff and grep mcp tool to document new tools")]
    near = {"summary": "run git diff and grep mcp tool to document new tools now"}
    far = {"summary": "battery status reads from system power management only"}
    assert pcl.is_duplicate(near, existing) is True
    assert pcl.is_duplicate(far, existing) is False
    assert pcl.is_duplicate({"summary": ""}, existing) is True  # empty == drop


def test_run_skips_when_ollama_unavailable(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "unavailable", "reason": "model not found"}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    result = pcl.run()
    assert result.startswith("skip: ollama unavailable")
    assert not inbox.exists()


def test_run_skips_low_signal(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return "file.py — role"

        @staticmethod
        def learn_extract_pattern(
            _findings, approve=False, repo_context="", require_repo_context=False,
            http_post=None,
        ):
            return {"confidence": "low", "evidence": [], "pattern_name": "x"}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("sha1", "some diff"))
    result = pcl.run()
    assert result.startswith("skip: low-signal")
    assert not inbox.exists()


def test_run_queues_grounded_candidate(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return "file.py — role"

        @staticmethod
        def learn_extract_pattern(
            _findings, approve=False, repo_context="", require_repo_context=False,
            http_post=None,
        ):
            return {
                "confidence": "high",
                "evidence": ["file.py line 1"],
                "pattern_name": "version drift guard",
                "summary": "keep pyproject version in sync with VERSION",
            }

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("deadbeef", "diff"))
    result = pcl.run()
    assert result.startswith("queued:")
    rec = json.loads(inbox.read_text().strip())
    assert rec["pattern_name"] == "version drift guard"
    assert rec["status"] == "pending"


def test_hook_runs_inside_the_uv_project():
    """The hook must resolve the interpreter from mq-mcp/, where pyproject lives.

    Regression: a bare `uv run python` from the repo root found no project, so
    learn_engine could not import `requests` and most commits were logged as
    "skip: ollama unavailable (requests unavailable ...)"; nothing was queued
    between 2026-07-04 and 2026-11-11.
    """
    hook = (ROOT / "scripts" / "post-commit").read_text(encoding="utf-8")
    assert (ROOT / "mq-mcp" / "pyproject.toml").exists()
    assert not (ROOT / "pyproject.toml").exists()
    assert 'APP="$ROOT/mq-mcp"' in hook
    assert 'uv run --project "$APP" python' in hook
    assert 'runner="uv run python"' not in hook


def test_hook_refreshes_the_repo_signal_export_before_extracting():
    """The 24h symbol index is refreshed by the hook, ahead of the extraction."""
    hook = (ROOT / "scripts" / "post-commit").read_text(encoding="utf-8")
    refresh = hook.index("repo-signal export . --symbol-index\n")
    extract = hook.index('"${runner[@]}" scripts/post_commit_learn.py')
    assert refresh < extract
    assert "command -v repo-signal" in hook


def test_run_names_missing_repo_context_instead_of_low_signal(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    called = []

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return ""

        @staticmethod
        def learn_extract_pattern(*_args, **_kwargs):
            called.append(True)
            return {"confidence": "low", "evidence": [], "pattern_name": "x"}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("sha1", "some diff"))
    result = pcl.run()
    assert result.startswith("skip: no verified repo context")
    assert "low-signal" not in result
    assert called == []
    assert not inbox.exists()


def test_hook_pins_the_commit_before_going_to_the_background():
    hook = (ROOT / "scripts" / "post-commit").read_text(encoding="utf-8")
    pin = hook.index("SHA=$(git rev-parse HEAD")
    background = hook.index('scripts/post_commit_learn.py "$SHA"')
    assert pin < background


def test_main_analyses_the_sha_it_is_given(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    seen = []
    monkeypatch.setattr(pcl, "run", lambda sha="HEAD": seen.append(sha) or "ok")

    monkeypatch.setattr(sys, "argv", ["post_commit_learn.py", "0123abc"])
    assert pcl.main() == 0
    monkeypatch.setattr(sys, "argv", ["post_commit_learn.py"])
    assert pcl.main() == 0
    # Anything that is not a plain SHA must never reach git as an argument.
    monkeypatch.setattr(sys, "argv", ["post_commit_learn.py", "--output=/tmp/x"])
    assert pcl.main() == 0

    assert seen == ["0123abc", "HEAD", "HEAD"]


def test_low_signal_reports_what_the_model_itself_said(monkeypatch, tmp_path):
    """Evidence dropped by grounding must be distinguishable from none offered."""
    _redirect_files(monkeypatch, tmp_path)

    class _Response:
        @staticmethod
        def json():
            return {"response": json.dumps({"confidence": "high", "evidence": ["a", "b"]})}

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return "file.py"

        @staticmethod
        def learn_extract_pattern(_findings, http_post=None, **_kwargs):
            # Stand in for the provider call, then for grounding dropping it all.
            pcl._record_provider_trace(http_post.__closure__[0].cell_contents, _Response())
            return {"confidence": "low", "evidence": [], "pattern_name": "x"}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("sha1", "some diff"))
    result = pcl.run()
    assert result == (
        "skip: low-signal after 3 attempt(s) (confidence=low, evidence=0; "
        "model said confidence=high, evidence=2)"
    )


def _engine(answers, calls):
    """Fake learn_engine whose model answers come from ``answers`` in order."""

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            return "file.py"

        @staticmethod
        def learn_extract_pattern(_findings, **_kwargs):
            calls.append(True)
            return answers[min(len(calls), len(answers)) - 1]

    return _Eng()


_LOW = {"confidence": "low", "evidence": [], "pattern_name": "x"}
_GOOD = {
    "confidence": "high",
    "evidence": ["file.py line 1"],
    "pattern_name": "retry finds it",
    "summary": "a second answer was usable where the first was not",
}


def test_a_low_answer_is_asked_again_and_the_usable_one_is_queued(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setitem(sys.modules, "learn_engine", _engine([_LOW, _GOOD], calls))
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("deadbeef", "diff"))

    result = pcl.run()

    assert result == "queued: retry finds it (confidence=high, attempt 2/3)"
    assert len(calls) == 2
    assert json.loads(inbox.read_text().strip())["pattern_name"] == "retry finds it"


def test_retries_are_bounded(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setitem(sys.modules, "learn_engine", _engine([_LOW], calls))
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("deadbeef", "diff"))

    result = pcl.run()

    assert result.startswith("skip: low-signal after 3 attempt(s)")
    assert len(calls) == pcl.MAX_ATTEMPTS == 3
    assert not inbox.exists()


def test_only_environment_failures_are_retried_later():
    assert pcl._retry_later("skip: ollama unavailable (Ollama endpoint unavailable: x)")
    assert pcl._retry_later("skip: no verified repo context (...)")
    assert pcl._retry_later(
        "skip: extraction failed: Ollama learn provider unavailable: Read timed out."
    )
    assert not pcl._retry_later("skip: low-signal after 3 attempt(s) (confidence=low, evidence=0)")
    assert not pcl._retry_later("skip: duplicate of an existing lesson/candidate (x)")
    assert not pcl._retry_later("skip: commit only touches learn_engine/memory/ (...)")
    assert not pcl._retry_later("queued: x (confidence=high)")


_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_C = "c" * 40


def test_pending_commits_are_remembered_once_and_bounded(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    monkeypatch.setattr(pcl, "MAX_PENDING", 2)

    pcl.remember_pending(_SHA_A)
    pcl.remember_pending(_SHA_A)
    pcl.remember_pending("--not-a-sha")
    assert pcl._read_pending() == [_SHA_A]

    pcl.remember_pending(_SHA_B)
    pcl.remember_pending(_SHA_C)
    assert pcl._read_pending() == [_SHA_B, _SHA_C]

    pcl.forget_pending(_SHA_B)
    pcl.forget_pending(_SHA_C)
    assert not pcl.PENDING_FILE.exists()


def test_main_keeps_a_commit_the_environment_could_not_analyse(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    monkeypatch.setattr(pcl, "run", lambda sha="HEAD": "skip: ollama unavailable (down)")
    monkeypatch.setattr(pcl, "_resolve", lambda sha: _SHA_A)
    monkeypatch.setattr(sys, "argv", ["post_commit_learn.py", _SHA_A])

    assert pcl.main() == 0

    assert pcl._read_pending() == [_SHA_A]
    assert "pending aaaaaaaaaaaa: kept for a later run" in pcl.LOG_FILE.read_text()


def test_main_drains_the_backlog_once_the_environment_works(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    pcl.remember_pending(_SHA_A)
    pcl.remember_pending(_SHA_B)
    seen = []
    monkeypatch.setattr(pcl, "run", lambda sha="HEAD": seen.append(sha) or "queued: x (confidence=high)")
    monkeypatch.setattr(pcl, "_resolve", lambda sha: "" if sha == _SHA_B else sha)
    monkeypatch.setattr(sys, "argv", ["post_commit_learn.py", _SHA_C])

    assert pcl.main() == 0

    # The current commit, then the backlog; a vanished commit never reaches run.
    assert seen == [_SHA_C, _SHA_A]
    assert pcl._read_pending() == []
    log = pcl.LOG_FILE.read_text()
    assert "backlog aaaaaaaaaaaa: queued: x" in log
    assert "backlog bbbbbbbbbbbb: dropped, commit no longer exists" in log


def test_drain_stops_when_the_environment_fails_again(monkeypatch, tmp_path):
    _redirect_files(monkeypatch, tmp_path)
    pcl.remember_pending(_SHA_A)
    pcl.remember_pending(_SHA_B)
    monkeypatch.setattr(pcl, "run", lambda sha="HEAD": "skip: ollama unavailable (down)")
    monkeypatch.setattr(pcl, "_resolve", lambda sha: sha)

    pcl.drain_pending()

    assert pcl._read_pending() == [_SHA_A, _SHA_B]


def test_hook_says_so_at_commit_time_when_ollama_is_down():
    hook = (ROOT / "scripts" / "post-commit").read_text(encoding="utf-8")
    notice = hook.index("Ollama is not running")
    background = hook.index('scripts/post_commit_learn.py "$SHA"')
    assert notice < background
    assert ">&2" in hook[notice : notice + 200]
    assert "curl -s -o /dev/null -m 1 http://localhost:11434/api/tags" in hook


def test_provider_trace_ignores_unparseable_answers():
    trace: dict = {}

    class _Bad:
        @staticmethod
        def json():
            return {"response": "not json"}

    pcl._record_provider_trace(trace, _Bad())
    pcl._record_provider_trace(trace, object())
    assert trace == {}


def _fake_git(name_status):
    def git(*args):
        if args[0] == "rev-parse":
            return "f" * 40 + "\n"
        if "--name-status" in args:
            return name_status
        if args[0] == "log":
            return "subject line\n"
        return "diff --git a/x b/x\n+changed\n"

    return git


def test_commit_findings_marks_a_commit_without_changed_files(monkeypatch):
    monkeypatch.setattr(pcl, "_git", _fake_git(""))
    assert pcl.commit_findings("HEAD") == ("f" * 40, pcl.NO_CHANGES)


def test_commit_findings_still_returns_text_for_a_real_change(monkeypatch):
    monkeypatch.setattr(pcl, "_git", _fake_git("M\tscripts/post-commit\n"))
    sha, findings = pcl.commit_findings("HEAD")
    assert sha == "f" * 40
    assert findings not in {pcl.NO_CHANGES, pcl.MEMORY_ONLY}
    assert "scripts/post-commit" in findings


def test_run_skips_a_commit_without_changed_files_before_asking_the_model(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setitem(sys.modules, "learn_engine", _engine([_LOW], calls))
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("deadbeef", pcl.NO_CHANGES))

    result = pcl.run()

    assert result == "skip: commit changes no files (empty or merge commit)"
    assert calls == []
    assert not pcl._retry_later(result)
    assert not inbox.exists()


def test_only_learn_memory_paths():
    paths = pcl._paths_from_name_status(
        "M\tlearn_engine/memory/lessons.jsonl\nR100\tlearn_engine/memory/a\tlearn_engine/memory/b"
    )
    assert paths == [
        "learn_engine/memory/lessons.jsonl",
        "learn_engine/memory/a",
        "learn_engine/memory/b",
    ]
    assert pcl._only_learn_memory(paths) is True
    assert pcl._only_learn_memory(paths + ["scripts/post-commit"]) is False
    assert pcl._only_learn_memory([]) is False


def test_run_skips_a_commit_that_only_touches_learn_memory(monkeypatch, tmp_path):
    inbox, _ = _redirect_files(monkeypatch, tmp_path)
    called = []

    class _Eng:
        @staticmethod
        def ollama_learn_status():
            return {"status": "ready"}

        @staticmethod
        def load_repo_context_snapshot(_root):
            called.append("context")
            return "file.py"

        @staticmethod
        def learn_extract_pattern(*_args, **_kwargs):
            called.append("model")
            return {}

    monkeypatch.setitem(sys.modules, "learn_engine", _Eng())
    monkeypatch.setattr(pcl, "commit_findings", lambda sha="HEAD": ("sha1", pcl.MEMORY_ONLY))
    result = pcl.run()
    assert result.startswith("skip: commit only touches learn_engine/memory/")
    assert called == []
    assert not inbox.exists()
