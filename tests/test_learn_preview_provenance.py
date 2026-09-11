"""The human-readable learn preview must name the source of its evidence.

ADR-007 keeps learn extraction fail-closed rather than falling back to a git
subprocess, and names visible provenance as the first precondition for ever
revisiting that. Until a reader can see which source produced the evidence in
front of them, no second source can be added safely.

These tests fix the rendering, not the fallback logic: what the preview says
for verified evidence, for refused evidence, and for a snapshot whose
provenance header is not the one this repo writes.
"""

import importlib.util
import json
import re
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mq-mcp"))

import server  # noqa: E402


def _load_engine():
    module_path = ROOT / "mq-mcp" / "learn_engine.py"
    spec = importlib.util.spec_from_file_location("learn_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["learn_engine"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_CANDIDATE = {
    "pattern_name": "safety-class-inference",
    "pattern_type": "safety",
    "summary": "SKILLS.md index text drives safety class.",
    "recommended_action": "Append read-only to SKILLS.md index lines.",
    "evidence": ["_infer_safety() scans SKILLS.md index text only"],
    "should_store": False,
    "confidence": "high",
}


class _OkResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"response": json.dumps(_CANDIDATE)}


def _write_export(repo_root: Path, generated_at: str, files: list[str]) -> None:
    exports = repo_root / ".repo-signal" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    for name in files:
        target = repo_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    exports.joinpath("symbol_index.json").write_text(
        json.dumps(
            {
                "schema": "symbol_index.v1",
                "repo_name": repo_root.name,
                "generated_at": generated_at,
                "files": [{"path": name} for name in files],
            }
        ),
        encoding="utf-8",
    )


def _stub_ollama(monkeypatch) -> None:
    """Install a fake `requests` for the engine's in-function import.

    Patching the real module is not safe here: another test in the suite
    replaces `sys.modules["requests"]` with a stub of its own, so these tests
    passed alone and failed in the suite. Owning the entry outright makes the
    result independent of test order.
    """
    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(post=lambda *a, **k: _OkResponse())
    )


def _fresh_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mq-mcp"
    repo.mkdir()
    generated_at = (
        datetime.now(timezone.utc) - timedelta(minutes=5)
    ).isoformat().replace("+00:00", "Z")
    _write_export(repo, generated_at, ["server.py", "README.md"])
    return repo


# --- the rendering itself -------------------------------------------------


def test_verified_evidence_names_repo_signal_as_the_primary_source():
    engine = _load_engine()
    snapshot = (
        "PROVENANCE source=repo-signal schema=symbol_index.v1 "
        "repo=mq-mcp generated_at=2026-08-11T10:00:00Z\n"
        "mq-mcp/server.py\n"
        "README.md"
    )
    lines = engine.render_repo_context_provenance(snapshot)
    rendered = "\n".join(lines)

    assert "repo context:" in rendered
    assert "repo-signal" in rendered
    assert "primary" in rendered
    assert "symbol_index.v1" in rendered
    assert "mq-mcp" in rendered
    assert "2026-08-11T10:00:00Z" in rendered
    assert "2 listed" in rendered


def test_truncated_snapshot_reports_how_many_files_were_omitted():
    engine = _load_engine()
    snapshot = "\n".join(
        [
            "PROVENANCE source=repo-signal schema=symbol_index.v1 "
            "repo=mq-mcp generated_at=2026-08-11T10:00:00Z",
            "a.py",
            "b.py",
            "... (17 more files omitted)",
        ]
    )
    rendered = "\n".join(engine.render_repo_context_provenance(snapshot))

    assert "2 listed" in rendered
    assert "17" in rendered


def test_absent_evidence_says_so_and_says_nothing_else_was_consulted():
    engine = _load_engine()
    rendered = "\n".join(engine.render_repo_context_provenance(""))

    assert "repo context:" in rendered
    assert "none" in rendered
    assert "repo-signal" in rendered
    # The reader must be able to tell refusal from a silent fallback.
    assert re.search(r"no other source", rendered)
    assert "primary" not in rendered


def test_a_snapshot_without_our_provenance_header_is_not_called_repo_signal():
    """A future second source must not inherit repo-signal's label by default."""
    engine = _load_engine()
    rendered = "\n".join(
        engine.render_repo_context_provenance("git ls-files output\nserver.py")
    )

    assert "unverified" in rendered
    assert "primary" not in rendered
    assert "source=repo-signal" not in rendered


def test_rendering_does_not_read_the_filesystem_or_run_anything(monkeypatch):
    engine = _load_engine()

    def _forbidden(*args, **kwargs):
        raise AssertionError("the preview layer must not execute a subprocess")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(Path, "read_text", _forbidden)

    engine.render_repo_context_provenance(
        "PROVENANCE source=repo-signal schema=symbol_index.v1 "
        "repo=mq-mcp generated_at=2026-08-11T10:00:00Z\nserver.py"
    )


# --- what the tools actually print ----------------------------------------


def test_ollama_learn_extract_preview_shows_verified_provenance(tmp_path, monkeypatch):
    repo = _fresh_repo(tmp_path)
    monkeypatch.setattr(server, "REPO_ROOT", repo)
    _stub_ollama(monkeypatch)

    out = server.ollama_learn_extract("SKILLS.md safety class detection failed.")

    assert "repo context:" in out
    assert "repo-signal" in out
    assert "primary" in out
    assert "symbol_index.v1" in out
    assert "DRY-RUN PREVIEW" in out


def test_ollama_learn_extract_preview_shows_refusal_provenance(tmp_path, monkeypatch):
    empty = tmp_path / "mq-mcp"
    empty.mkdir()
    monkeypatch.setattr(server, "REPO_ROOT", empty)

    out = server.ollama_learn_extract("SKILLS.md safety class detection failed.")

    assert "repo context:" in out
    assert "none" in out
    assert "no other source" in out


def test_last_review_preview_shows_verified_provenance(tmp_path, monkeypatch):
    repo = _fresh_repo(tmp_path)
    monkeypatch.setattr(server, "REPO_ROOT", repo)
    _stub_ollama(monkeypatch)

    class _Entry:
        findings_text = "BLOCKING: missing safety class on new tool."

    import review_engine.review_memory as rm

    monkeypatch.setattr(rm.ReviewMemory, "get_last", lambda self, path, repo=None: _Entry())

    out = server.learn_extract_from_last_review("server.py")

    assert "repo context:" in out
    assert "repo-signal" in out
    assert "primary" in out


def test_last_review_preview_shows_refusal_provenance(tmp_path, monkeypatch):
    empty = tmp_path / "mq-mcp"
    empty.mkdir()
    monkeypatch.setattr(server, "REPO_ROOT", empty)

    class _Entry:
        findings_text = "BLOCKING: missing safety class on new tool."

    import review_engine.review_memory as rm

    monkeypatch.setattr(rm.ReviewMemory, "get_last", lambda self, path, repo=None: _Entry())

    out = server.learn_extract_from_last_review("server.py")

    assert "repo context:" in out
    assert "none" in out


def test_preview_layer_executes_no_subprocess(tmp_path, monkeypatch):
    """ADR-007: the preview shows provenance; it never widens the source."""
    empty = tmp_path / "mq-mcp"
    empty.mkdir()
    monkeypatch.setattr(server, "REPO_ROOT", empty)

    def _forbidden(*args, **kwargs):
        raise AssertionError("the preview layer must not execute a subprocess")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(subprocess, "check_output", _forbidden)

    out = server.ollama_learn_extract("SKILLS.md safety class detection failed.")
    assert "none" in out


# --- the machine-readable side must not move ------------------------------


def test_the_prompt_provenance_header_is_unchanged(tmp_path):
    """The model still receives the same PROVENANCE line it received before."""
    engine = _load_engine()
    repo = _fresh_repo(tmp_path)

    snapshot = engine.load_repo_context_snapshot(repo)
    assert snapshot.splitlines()[0].startswith(
        "PROVENANCE source=repo-signal schema=symbol_index.v1 repo=mq-mcp generated_at="
    )

    sent = {}

    def _capture(endpoint, json=None, timeout=None):
        sent["prompt"] = json["prompt"]
        return _OkResponse()

    engine.ollama_learn_extract(
        "findings",
        repo_context=snapshot,
        require_repo_context=True,
        http_post=_capture,
    )
    assert "PROVENANCE source=repo-signal schema=symbol_index.v1" in sent["prompt"]
