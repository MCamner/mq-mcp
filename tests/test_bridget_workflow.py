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
