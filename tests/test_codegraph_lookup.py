"""CLI contract tests for Bridget's supported CodeGraph symbol lookup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import codegraph_lookup as lookup  # noqa: E402


def test_parse_symbol_args_accepts_repo_and_file():
    parsed = lookup.parse_symbol_args(
        ["--symbol", "BridgetContext", "--repo", "mq-mcp", "--file", "mq-mcp/bridget_context.py"]
    )

    assert parsed == ("BridgetContext", "mq-mcp", "mq-mcp/bridget_context.py")


@pytest.mark.parametrize(
    "argv",
    [
        ["--symbol"],
        ["--symbol", "Name", "extra"],
        ["--symbol", "Name", "--unknown", "x"],
        ["--symbol", "Name", "--repo"],
        ["--symbol", "Name", "--repo", "a", "--repo", "b"],
    ],
)
def test_parse_symbol_args_rejects_invalid_input(argv):
    with pytest.raises(ValueError):
        lookup.parse_symbol_args(argv)


def test_handle_symbol_delegates_with_argv_and_prints_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lookup, "resolve_repo", lambda _target: tmp_path)
    monkeypatch.setattr(lookup.shutil, "which", lambda _name: "/opt/bin/codegraph")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="symbol output\n", stderr="")

    monkeypatch.setattr(lookup.subprocess, "run", fake_run)

    rc = lookup.handle_symbol("Thing", repo="mq-mcp", file_path="src/thing.py")

    assert rc == 0
    assert capsys.readouterr().out == "symbol output\n"
    command, kwargs = calls[0]
    assert command == [
        "/opt/bin/codegraph",
        "--no-color",
        "node",
        "--path",
        str(tmp_path),
        "--file",
        "src/thing.py",
        "Thing",
    ]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == lookup.CODEGRAPH_TIMEOUT


def test_handle_symbol_preserves_delegate_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lookup, "resolve_repo", lambda _target: tmp_path)
    monkeypatch.setattr(lookup.shutil, "which", lambda _name: "/opt/bin/codegraph")
    monkeypatch.setattr(
        lookup.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 7, stdout="", stderr="lookup failed\n"
        ),
    )

    assert lookup.handle_symbol("Missing") == 7
    assert capsys.readouterr().err == "lookup failed\n"


def test_dispatcher_returns_none_for_unrelated_arguments(monkeypatch):
    monkeypatch.setattr(lookup, "handle_symbol", lambda *args, **kwargs: 0)

    assert lookup.maybe_handle_symbol(["plain prompt"]) is None
    assert lookup.maybe_handle_symbol(["--history"]) is None


def test_dispatcher_reports_usage_error_without_calling_handler(monkeypatch, capsys):
    called = False

    def fake_handle(*args, **kwargs):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(lookup, "handle_symbol", fake_handle)

    assert lookup.maybe_handle_symbol(["--symbol"]) == 2
    assert called is False
    assert "usage" in capsys.readouterr().err.lower()


def test_parse_dependency_args_defaults_to_both():
    assert lookup.parse_dependency_args(["--dependencies", "run_turn"]) == (
        "run_turn",
        None,
        "both",
        20,
    )


def test_parse_dependency_args_accepts_all_options():
    assert lookup.parse_dependency_args(
        [
            "--dependencies",
            "run_turn",
            "--repo",
            "mq-mcp",
            "--direction",
            "callers",
            "--limit",
            "7",
        ]
    ) == ("run_turn", "mq-mcp", "callers", 7)


@pytest.mark.parametrize(
    "argv",
    [
        ["--dependencies"],
        ["--dependencies", "Name", "extra"],
        ["--dependencies", "Name", "--direction", "sideways"],
        ["--dependencies", "Name", "--limit", "0"],
        ["--dependencies", "Name", "--limit", "101"],
        ["--dependencies", "Name", "--limit", "many"],
    ],
)
def test_parse_dependency_args_rejects_invalid_input(argv):
    with pytest.raises(ValueError):
        lookup.parse_dependency_args(argv)


def test_handle_dependencies_runs_callers_then_callees(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lookup, "resolve_repo", lambda _target: tmp_path)
    monkeypatch.setattr(lookup.shutil, "which", lambda _name: "/opt/bin/codegraph")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command, 0, stdout=f"{command[2]} output\n", stderr=""
        )

    monkeypatch.setattr(lookup.subprocess, "run", fake_run)

    assert lookup.handle_dependencies("run_turn", direction="both", limit=5) == 0
    assert calls == [
        [
            "/opt/bin/codegraph",
            "--no-color",
            "callers",
            "--path",
            str(tmp_path),
            "--limit",
            "5",
            "run_turn",
        ],
        [
            "/opt/bin/codegraph",
            "--no-color",
            "callees",
            "--path",
            str(tmp_path),
            "--limit",
            "5",
            "run_turn",
        ],
    ]
    out = capsys.readouterr().out
    assert "## Callers of run_turn" in out
    assert "callers output" in out
    assert "## Callees of run_turn" in out
    assert "callees output" in out


def test_handle_dependencies_stops_and_preserves_first_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lookup, "resolve_repo", lambda _target: tmp_path)
    monkeypatch.setattr(lookup.shutil, "which", lambda _name: "/opt/bin/codegraph")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 9, stdout="", stderr="bad graph\n")

    monkeypatch.setattr(lookup.subprocess, "run", fake_run)

    assert lookup.handle_dependencies("missing", direction="both") == 9
    assert len(calls) == 1
    assert capsys.readouterr().err == "bad graph\n"


def test_dispatcher_routes_dependencies(monkeypatch):
    calls = []
    monkeypatch.setattr(
        lookup,
        "handle_dependencies",
        lambda *args, **kwargs: calls.append((args, kwargs)) or 0,
    )

    assert lookup.maybe_handle_lookup(
        ["--dependencies", "run_turn", "--direction", "callees"]
    ) == 0
    assert calls == [(('run_turn',), {"repo": None, "direction": "callees", "limit": 20})]


def test_parse_graph_search_args_defaults_max_files():
    assert lookup.parse_graph_search_args(
        ["--graph-search", "call-graph hotspots"]
    ) == ("call-graph hotspots", None, 8)


def test_parse_graph_search_args_accepts_repo_and_max_files():
    assert lookup.parse_graph_search_args(
        [
            "--graph-search",
            "paths from run_turn",
            "--repo",
            "mq-mcp",
            "--max-files",
            "5",
        ]
    ) == ("paths from run_turn", "mq-mcp", 5)


@pytest.mark.parametrize(
    "argv",
    [
        ["--graph-search"],
        ["--graph-search", "query", "extra"],
        ["--graph-search", "query", "--unknown", "x"],
        ["--graph-search", "query", "--max-files", "0"],
        ["--graph-search", "query", "--max-files", "21"],
        ["--graph-search", "query", "--max-files", "many"],
    ],
)
def test_parse_graph_search_args_rejects_invalid_input(argv):
    with pytest.raises(ValueError):
        lookup.parse_graph_search_args(argv)


def test_handle_graph_search_delegates_to_explore(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lookup, "resolve_repo", lambda _target: tmp_path)
    monkeypatch.setattr(lookup.shutil, "which", lambda _name: "/opt/bin/codegraph")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="graph paths\n", stderr="")

    monkeypatch.setattr(lookup.subprocess, "run", fake_run)

    assert lookup.handle_graph_search("call hotspots", repo="mq-mcp", max_files=5) == 0
    assert capsys.readouterr().out == "graph paths\n"
    command, kwargs = calls[0]
    assert command == [
        "/opt/bin/codegraph",
        "--no-color",
        "explore",
        "--path",
        str(tmp_path),
        "--max-files",
        "5",
        "call hotspots",
    ]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == lookup.CODEGRAPH_TIMEOUT


def test_dispatcher_routes_graph_search(monkeypatch):
    calls = []
    monkeypatch.setattr(
        lookup,
        "handle_graph_search",
        lambda *args, **kwargs: calls.append((args, kwargs)) or 0,
    )

    assert lookup.maybe_handle_lookup(
        ["--graph-search", "hotspots", "--max-files", "4"]
    ) == 0
    assert calls == [(('hotspots',), {"repo": None, "max_files": 4})]
