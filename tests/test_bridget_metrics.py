import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "bridget_metrics.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))


@pytest.fixture(autouse=True)
def _enable_metrics_for_unit_tests(monkeypatch):
    """validate.sh disables runtime collection; unit tests use isolated paths."""
    monkeypatch.delenv("BRIDGET_METRICS_DISABLED", raising=False)


def load_module():
    spec = importlib.util.spec_from_file_location("mq_mcp_bridget_metrics", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_record_writes_only_the_metric_contract(tmp_path):
    metrics_module = load_module()
    path = tmp_path / "bridget-metrics.jsonl"
    metrics = metrics_module.BridgetMetrics(path)

    assert metrics.record("commands", now=date(2026, 8, 14)) is True

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row == {
        "schema": "bridget-metric.v1",
        "date": "2026-08-14",
        "metric": "commands",
        "count": 1,
    }


def test_record_rejects_unknown_or_invalid_counters(tmp_path):
    metrics_module = load_module()
    path = tmp_path / "bridget-metrics.jsonl"
    metrics = metrics_module.BridgetMetrics(path)

    assert metrics.record("prompt_text", now=date(2026, 8, 14)) is False
    assert metrics.record("commands", count=0, now=date(2026, 8, 14)) is False
    assert not path.exists()


def test_record_can_be_disabled_for_ci_and_smoke_tests(tmp_path, monkeypatch):
    metrics_module = load_module()
    path = tmp_path / "bridget-metrics.jsonl"
    metrics = metrics_module.BridgetMetrics(path)
    monkeypatch.setenv("BRIDGET_METRICS_DISABLED", "1")

    assert metrics.record("commands", now=date(2026, 8, 14)) is False
    assert not path.exists()


def test_daily_aggregates_known_rows_and_ignores_bad_data(tmp_path):
    metrics_module = load_module()
    path = tmp_path / "bridget-metrics.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"schema":"bridget-metric.v1","date":"2026-08-13","metric":"commands","count":2}',
                '{"schema":"bridget-metric.v1","date":"2026-08-13","metric":"sessions","count":1}',
                '{"schema":"bridget-metric.v1","date":"2026-08-14","metric":"delegations","count":1}',
                '{"schema":"bridget-metric.v1","date":"2026-07-01","metric":"commands","count":99}',
                '{"schema":"wrong","date":"2026-08-14","metric":"commands","count":99}',
                '{"schema":"bridget-metric.v1","date":"2026-08-14","metric":"prompt","count":99}',
                "not json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    metrics = metrics_module.BridgetMetrics(path)

    rows = metrics.daily(days=2, now=date(2026, 8, 14))

    assert [row["date"] for row in rows] == ["2026-08-13", "2026-08-14"]
    assert rows[0]["commands"] == 2
    assert rows[0]["sessions"] == 1
    assert rows[1]["delegations"] == 1
    assert rows[1]["commands"] == 0


def test_dashboard_uses_outcome_labels_and_totals(tmp_path):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")
    metrics.record("commands", count=3, now=date(2026, 8, 14))
    metrics.record("learning_suggestions", now=date(2026, 8, 14))
    metrics.record("accepted_learning", now=date(2026, 8, 14))

    output = metrics.dashboard(days=1, now=date(2026, 8, 14))

    assert "Bridget metrics — last 1 day" in output
    assert "helped" in output
    assert "delegated" in output
    assert "suggested" in output
    assert "accepted" in output
    assert "2026-08-14" in output
    assert "Total" in output
    assert "3" in output


def test_command_handler_accepts_an_optional_day_count(tmp_path, capsys):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")

    assert metrics_module.maybe_handle_metrics_command(
        ["--metrics", "14"], metrics=metrics
    ) is True
    assert "last 14 days" in capsys.readouterr().out


def test_command_handler_rejects_invalid_usage(tmp_path, capsys):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")

    assert metrics_module.maybe_handle_metrics_command(
        ["--metrics", "0"], metrics=metrics
    ) is True
    assert "ERROR: usage: bridget --metrics [1-365]" in capsys.readouterr().out


def test_validation_report_is_explicit_when_no_evidence_exists(tmp_path):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")

    output = metrics.validation_report(days=30, now=date(2026, 8, 14))

    assert "Bridget Phase 7 validation — last 30 days" in output
    assert "Evidence status: insufficient (no recorded usage)" in output
    assert "Active days: 0/30" in output
    assert "Usefulness cannot be established from aggregate counters alone." in output
    assert "Need for more memory: not established." in output


def test_validation_report_calculates_only_transparent_ratios(tmp_path):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")
    metrics.record("sessions", count=4, now=date(2026, 8, 13))
    metrics.record("commands", count=8, now=date(2026, 8, 13))
    metrics.record("delegations", count=2, now=date(2026, 8, 13))
    metrics.record("learning_suggestions", count=4, now=date(2026, 8, 14))
    metrics.record("accepted_learning", count=1, now=date(2026, 8, 14))
    metrics.record("history_hits", count=3, now=date(2026, 8, 14))
    metrics.record("context_hits", count=2, now=date(2026, 8, 14))

    output = metrics.validation_report(days=2, now=date(2026, 8, 14))

    assert "Evidence status: observation in progress" in output
    assert "Active days: 2/2" in output
    assert "Delegation rate: 25.0% (2/8 commands)" in output
    assert "Learning acceptance: 25.0% (1/4 suggestions)" in output
    assert "Context reuse: 5 hits (3 history, 2 project/repo)" in output


def test_validation_command_accepts_optional_day_count(tmp_path, capsys):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")

    assert metrics_module.maybe_handle_validation_command(
        ["--validation", "30"], metrics=metrics
    ) is True
    assert "last 30 days" in capsys.readouterr().out


def test_validation_command_rejects_invalid_usage(tmp_path, capsys):
    metrics_module = load_module()
    metrics = metrics_module.BridgetMetrics(tmp_path / "bridget-metrics.jsonl")

    assert metrics_module.maybe_handle_validation_command(
        ["--validation", "366"], metrics=metrics
    ) is True
    assert "ERROR: usage: bridget --validation [1-365]" in capsys.readouterr().out
