"""Tests for the Bridget workflow entrypoint (Phase 8).

Locks the boundary: Bridget proposes a known template deterministically,
delegates plan/run to mq-agent with the workflow depth guard set, requires
explicit approval before running, and refuses to start a workflow from inside
one. Bridget holds no run state and never starts `mqlaunch flow` from an MCP tool.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import bridget_workflow as bw  # noqa: E402

MODULE_SRC = (ROOT / "mq-mcp" / "bridget_workflow.py").read_text(encoding="utf-8")


# --- deterministic classification ------------------------------------------

def test_classify_goal_matches_each_template():
    assert bw.classify_goal("run preflight on the repo") == "repo-preflight"
    assert bw.classify_goal("do a code review and run tests") == "review-and-test"
    assert bw.classify_goal("is this ready to ship a release") == "release-ready"


def test_classify_goal_no_match_returns_none():
    assert bw.classify_goal("do the thing") is None
    assert bw.classify_goal("") is None


def test_classify_goal_ambiguous_returns_none():
    # Keywords for two templates -> do not guess.
    assert bw.classify_goal("review and run preflight doctor") is None


# --- repo identification ----------------------------------------------------

def test_identify_repo_defaults_to_cwd(tmp_path):
    assert bw.identify_repo("run preflight", cwd=tmp_path) == tmp_path.resolve()


def test_identify_repo_explicit_path_wins(tmp_path):
    target = tmp_path / "somerepo"
    target.mkdir()
    goal = f"preflight {target}"
    assert bw.identify_repo(goal, cwd=tmp_path) == target.resolve()


# --- recursion guard --------------------------------------------------------

def test_recursion_guard_refuses_when_depth_set(monkeypatch):
    monkeypatch.setenv("MQ_WORKFLOW_DEPTH", "1")
    called = []
    monkeypatch.setattr(bw, "_invoke_mq_agent", lambda *a, **k: called.append(a) or ("", 0))
    rc = bw.run_workflow_entry("run preflight")
    assert rc == 1
    assert called == []  # never reached mq-agent


# --- delegation + approval --------------------------------------------------

def _capture_invoker(record):
    def _invoke(args, *, capture=True):
        record.append((tuple(args), capture))
        if args[:2] == ["workflow", "plan"]:
            return ('{"template": "repo-preflight", "repo": "/x", "steps": []}', 0)
        return ("", 0)
    return _invoke


def test_run_invokes_plan_then_run_with_repo(monkeypatch):
    record: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    rc = bw.run_workflow_entry("run preflight", assume_yes=True)
    assert rc == 0
    plan_args = record[0][0]
    run_args = record[1][0]
    assert plan_args[:2] == ("workflow", "plan")
    assert "--repo" in plan_args
    assert run_args[:2] == ("workflow", "run")
    assert "--repo" in run_args
    assert "--yes" in run_args  # Bridget's y/N is the start gate; no double prompt


def test_decline_does_not_run(monkeypatch):
    record: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    monkeypatch.setattr(bw, "_read_line", lambda prompt: "n")
    rc = bw.run_workflow_entry("run preflight")
    assert rc == 0
    invoked = [args[:2] for (args, _capture) in record]
    assert ("workflow", "plan") in invoked
    assert ("workflow", "run") not in invoked


def test_no_template_selected_does_not_run(monkeypatch):
    record: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    monkeypatch.setattr(bw, "_read_line", lambda prompt: "")  # cancel the picker
    rc = bw.run_workflow_entry("do the thing")
    assert rc == 0
    assert record == []  # never planned or ran


# --- child env carries the depth guard --------------------------------------

def test_invoke_sets_depth_guard_in_child_env(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        captured["cwd"] = kwargs.get("cwd")

        class R:
            stdout = "{}"
            stderr = ""
            returncode = 0
        return R()

    monkeypatch.setenv("MQ_AGENT_HOME", str(tmp_path))
    monkeypatch.setattr(bw.subprocess, "run", fake_run)
    out, rc = bw._invoke_mq_agent(["workflow", "plan", "repo-preflight", "--repo", "/x"])
    assert rc == 0
    assert captured["env"].get("MQ_WORKFLOW_DEPTH") == "1"
    assert "VIRTUAL_ENV" not in captured["env"]
    assert captured["cmd"][:4] == ["uv", "--project", str(tmp_path), "run"]


def test_invoke_missing_mq_agent_is_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MQ_AGENT_HOME", str(tmp_path / "nope"))
    out, rc = bw._invoke_mq_agent(["workflow", "list"])
    assert rc == 127
    assert "mq-agent not found" in out


# --- boundary guards --------------------------------------------------------

def test_module_holds_no_run_state_or_shell_chains():
    # Bridget must not persist workflow state, retry, or build free shell chains.
    forbidden = ("WorkflowStore", "save_run", "shell_exec", "shell=True")
    for token in forbidden:
        assert token not in MODULE_SRC, f"boundary leak: {token}"


def test_run_mqlaunch_refuses_flow():
    import server
    out, rc = server._run_mqlaunch("flow", "run", "repo-preflight")
    assert rc == 1
    assert "may not start" in out


# --- delegation is reported so it can be measured ----------------------------

def test_on_delegated_called_after_run(monkeypatch):
    record: list = []
    seen: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    rc = bw.run_workflow_entry(
        "run preflight", assume_yes=True,
        on_delegated=lambda goal, template, rc: seen.append((goal, template, rc)),
    )
    assert rc == 0
    assert seen == [("run preflight", "repo-preflight", 0)]


def test_on_delegated_not_called_when_declined(monkeypatch):
    seen: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker([]))
    monkeypatch.setattr(bw, "_read_line", lambda prompt: "n")
    bw.run_workflow_entry("run preflight", on_delegated=lambda *a: seen.append(a))
    assert seen == []


# --- shortcuts: read-only mq-agent commands ----------------------------------
#
# Shortcuts sit beside the workflow templates for common read-only questions.
# Bridget builds the argv itself and never adds a write flag: fix-ci stays a
# diagnosis (no --approve) and pr review stays local (no --post).

def test_classify_goal_matches_each_shortcut():
    assert bw.classify_goal("ci is failing on main") == "ci-diagnose"
    assert bw.classify_goal("fix ci please") == "ci-diagnose"
    assert bw.classify_goal("ci fallerar") == "ci-diagnose"
    assert bw.classify_goal("show stack status") == "stack-status"
    assert bw.classify_goal("hur ser stackstatus ut") == "stack-status"
    assert bw.classify_goal("review pr 455") == "pr-review"
    assert bw.classify_goal("granska pr #12") == "pr-review"


def test_a_longer_phrase_wins_over_a_keyword_inside_it():
    # "health" is a repo-preflight keyword, but here it is part of "stack health".
    assert bw.classify_goal("check stack health") == "stack-status"
    # "review" is a review-and-test keyword, but here it is part of "review pr".
    assert bw.classify_goal("review PR #455") == "pr-review"
    # A plain review of the working diff is still review-and-test.
    assert bw.classify_goal("review my diff") == "review-and-test"


def test_independent_matches_stay_ambiguous():
    # Two intents named by separate keywords: ask, do not guess.
    assert bw.classify_goal("fix ci and run preflight") is None


def test_shortcut_argv_never_carries_a_write_flag(tmp_path):
    argv = {
        "ci-diagnose": bw.shortcut_argv("ci-diagnose", tmp_path, None),
        "stack-status": bw.shortcut_argv("stack-status", tmp_path, None),
        "pr-review": bw.shortcut_argv("pr-review", tmp_path, 455),
    }
    assert argv["ci-diagnose"] == ["fix-ci", str(tmp_path)]
    assert argv["stack-status"] == ["stack", "status"]
    assert argv["pr-review"] == ["pr", "review", "455", "--repo", str(tmp_path)]
    for args in argv.values():
        assert "--approve" not in args and "--post" not in args


def test_pr_number_is_read_from_the_goal():
    assert bw.pr_number("review pr 455") == 455
    assert bw.pr_number("granska PR #12 i mq-mcp") == 12
    assert bw.pr_number("review pull request 7") == 7
    assert bw.pr_number("review the pr") is None


def test_shortcut_runs_the_command_after_approval(monkeypatch, tmp_path):
    record: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    seen: list = []
    rc = bw.run_workflow_entry(
        "review pr 455", assume_yes=True,
        on_delegated=lambda goal, name, rc: seen.append((name, rc)),
    )
    assert rc == 0
    assert record == [(("pr", "review", "455", "--repo", str(tmp_path.resolve())), False)]
    assert seen == [("pr-review", 0)]


def test_declined_shortcut_runs_nothing(monkeypatch):
    record: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    monkeypatch.setattr(bw, "_read_line", lambda prompt: "n")
    assert bw.run_workflow_entry("show stack status") == 0
    assert record == []


def test_pr_review_without_a_number_asks_and_cancels_on_blank(monkeypatch):
    record: list = []
    prompts: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    monkeypatch.setattr(bw, "_read_line", lambda prompt: prompts.append(prompt) or "")
    assert bw.run_workflow_entry("review pr", assume_yes=True) == 0
    assert record == []
    assert any("PR number" in p for p in prompts)


def test_picker_offers_shortcuts_too(monkeypatch, capsys):
    record: list = []
    monkeypatch.delenv("MQ_WORKFLOW_DEPTH", raising=False)
    monkeypatch.setattr(bw, "_invoke_mq_agent", _capture_invoker(record))
    choice = str(bw.KNOWN_INTENTS.index("stack-status") + 1)
    monkeypatch.setattr(bw, "_read_line", lambda prompt: choice)
    assert bw.run_workflow_entry("do the thing", assume_yes=True) == 0
    assert "stack-status" in capsys.readouterr().out
    assert record == [(("stack", "status"), False)]
