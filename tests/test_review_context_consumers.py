"""What the review pipeline is actually given, and what it tells the operator.

The model is replaced by a client that records the prompt it was handed, so
these assertions are about the context the pipeline injected — not about
anything a model said.

ADR-008: the builder-internal flat map is not review evidence. Review consumes
generated/architecture/architecture_map.json, from the repo under review, and
reports the status of what it consumed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mq-mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("mq_mcp_server_context", SERVER_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MODEL_OUTPUT = "[NOTE] README.md:1\nNothing of consequence.\n"


class _FakeCompletions:
    def __init__(self, text, calls):
        self._text, self._calls = text, calls

    def create(self, **kwargs):
        self._calls.append(kwargs["messages"][1]["content"])
        return type("_R", (), {"choices": [
            type("_C", (), {"message": type("_M", (), {"content": self._text})()})()
        ]})()


class _FakeClient:
    def __init__(self, text, calls):
        self.chat = type("_Chat", (), {"completions": _FakeCompletions(text, calls)})()


@pytest.fixture
def fake_openai(monkeypatch):
    calls: list[str] = []

    def _install(text=MODEL_OUTPUT):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setitem(sys.modules, "openai", type(
            "_FakeOpenAIModule", (),
            {"OpenAI": staticmethod(lambda api_key: _FakeClient(text, calls))},
        ))
        return calls

    return _install


def _foreign_repo(tmp_path: Path, name: str = "repo-signal") -> Path:
    """A repo that is not mq-mcp, containing a path mq-mcp also has."""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    (repo / "README.md").write_text("# Other project\n", encoding="utf-8")
    (repo / ".mq").mkdir()
    (repo / ".mq" / "repo-contract.json").write_text(
        json.dumps({"repo": name}), encoding="utf-8"
    )
    return repo


def _canonical(repo: Path, *, repo_name: str, role: str = "documentation",
               age: timedelta = timedelta(hours=1), schema: str = "architecture_map.v1") -> Path:
    out = repo / "generated" / "architecture"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "architecture_map.json"
    path.write_text(json.dumps({
        "schema": schema,
        "repo_name": repo_name,
        "generated_at": (datetime.now(timezone.utc) - age).isoformat(),
        "file_count": 1,
        "files": {"README.md": {
            "role": role, "public_symbols": [], "last_review_timestamp": None, "hub_score": 0,
        }},
    }), encoding="utf-8")
    return path


def _flat_map(repo: Path, role: str = "project readme") -> None:
    """The builder-internal map, which review must no longer read."""
    ctx = repo / "review_engine" / "context"
    ctx.mkdir(parents=True, exist_ok=True)
    (ctx / "architecture_map.json").write_text(
        json.dumps({"README.md": role}), encoding="utf-8"
    )


def _review(monkeypatch, repo: Path, **kw) -> str:
    monkeypatch.setattr(_mod, "resolve_allowed_local_file", lambda p: repo)
    return _mod.review_file("README.md", mode="comment", repo_path=str(repo), **kw)


# ── the cross-repo leak this closes ──────────────────────────────────────────

def test_a_foreign_repo_does_not_inherit_this_repos_roles(tmp_path, fake_openai, monkeypatch):
    """Reviewing another repo used to inject mq-mcp's own architecture map.

    _load_architecture_role read REPO_ROOT regardless of which repo was under
    review, so any path that collided — README.md does — was described to the
    model using mq-mcp's role for it.
    """
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _flat_map(repo)  # present, and must be ignored

    _review(monkeypatch, repo)

    assert "Architecture role:" not in calls[0], calls[0]
    assert "project readme" not in calls[0]


def test_a_foreign_repo_uses_its_own_verified_artifact(tmp_path, fake_openai, monkeypatch):
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="repo-signal", role="the other project's readme")

    _review(monkeypatch, repo)

    assert "Architecture role: the other project's readme" in calls[0]


def test_an_artifact_declaring_another_repo_is_refused(tmp_path, fake_openai, monkeypatch):
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="mq-mcp", role="somebody else's role")

    output = _review(monkeypatch, repo)

    assert "Architecture role:" not in calls[0]
    assert "somebody else's role" not in calls[0]
    assert "repo-mismatch" in output


# ── the flat map is no longer evidence ───────────────────────────────────────

def test_the_builder_internal_map_is_not_read(tmp_path, fake_openai, monkeypatch):
    """A flat map present, a canonical artifact absent: no role, and it says so."""
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _flat_map(repo)

    output = _review(monkeypatch, repo)

    assert "Architecture role:" not in calls[0]
    assert "project readme" not in calls[0]
    assert "artifact-missing" in output


def test_the_canonical_artifact_wins_over_a_disagreeing_flat_map(tmp_path, fake_openai, monkeypatch):
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _flat_map(repo, role="stale flat role")
    _canonical(repo, repo_name="repo-signal", role="verified role")

    _review(monkeypatch, repo)

    assert "Architecture role: verified role" in calls[0]
    assert "stale flat role" not in calls[0]


# ── provenance the operator can see ──────────────────────────────────────────

def test_verified_context_is_reported_in_the_output(tmp_path, fake_openai, monkeypatch):
    fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="repo-signal")

    output = _review(monkeypatch, repo)

    assert "Context" in output
    assert "architecture_map.v1" in output
    assert "repo-signal" in output
    assert "verified" in output


def test_missing_context_is_reported_rather_than_hidden(tmp_path, fake_openai, monkeypatch):
    fake_openai()
    repo = _foreign_repo(tmp_path)

    output = _review(monkeypatch, repo)

    assert "unavailable" in output
    assert "artifact-missing" in output


def test_stale_context_is_used_and_its_age_shown(tmp_path, fake_openai, monkeypatch):
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="repo-signal", role="still true", age=timedelta(days=108))

    output = _review(monkeypatch, repo)

    assert "Architecture role: still true" in calls[0]
    assert "stale" in output
    assert "2592h" in output


def test_a_refused_artifact_names_the_reason(tmp_path, fake_openai, monkeypatch):
    fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="repo-signal", schema="architecture_map.v2")

    output = _review(monkeypatch, repo)

    assert "unavailable" in output
    assert "schema-mismatch" in output


def test_provenance_does_not_leak_the_repo_path(tmp_path, fake_openai, monkeypatch):
    fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="repo-signal")

    output = _review(monkeypatch, repo)

    assert str(tmp_path) not in output


# ── risk_review_file is the same pipeline ────────────────────────────────────

def _risk(monkeypatch, repo: Path) -> str:
    """risk_review_file has no repo_path, so it reviews whatever REPO_ROOT is.

    The temp repo therefore has to carry the contract the tool loads.
    """
    contracts = repo / "reviews" / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    (contracts / "security-review.md").write_text(
        (ROOT / "reviews" / "contracts" / "security-review.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    monkeypatch.setattr(_mod, "resolve_repo_file", lambda p: repo / p)
    return _mod.risk_review_file("README.md", mode="security")


def test_risk_review_reports_context_status_too(tmp_path, fake_openai, monkeypatch):
    fake_openai()
    repo = _foreign_repo(tmp_path)
    _canonical(repo, repo_name="repo-signal")

    output = _risk(monkeypatch, repo)

    assert "Context" in output
    assert "verified" in output


def test_risk_review_does_not_read_the_flat_map(tmp_path, fake_openai, monkeypatch):
    calls = fake_openai()
    repo = _foreign_repo(tmp_path)
    _flat_map(repo)

    _risk(monkeypatch, repo)

    assert "project readme" not in calls[0]


# ── cross-file context takes roles from the same evidence ────────────────────

def test_cross_file_context_uses_verified_roles(tmp_path, monkeypatch):
    repo = _foreign_repo(tmp_path)
    (repo / "app.py").write_text("import lib\n", encoding="utf-8")
    (repo / "lib.py").write_text("x = 1\n", encoding="utf-8")
    cg = repo / "review_engine" / "context"
    cg.mkdir(parents=True, exist_ok=True)
    (cg / "callgraph.json").write_text(json.dumps({
        "imports": {"app.py": ["lib.py"]}, "importers": {}, "hub_files": [], "symbols": {},
    }), encoding="utf-8")
    _flat_map(repo)

    out = repo / "generated" / "architecture"
    out.mkdir(parents=True, exist_ok=True)
    (out / "architecture_map.json").write_text(json.dumps({
        "schema": "architecture_map.v1",
        "repo_name": "repo-signal",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 1,
        "files": {"lib.py": {"role": "verified library role", "public_symbols": [],
                             "last_review_timestamp": None, "hub_score": 0}},
    }), encoding="utf-8")

    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    context = _mod._review_context_for(repo)
    block = _mod._build_rich_cross_file_context("app.py", context=context)

    assert "Role: verified library role" in block
    assert "project readme" not in block


def test_the_repo_is_identified_by_contract_not_by_directory(tmp_path, fake_openai, monkeypatch):
    """A worktree's directory differs from the repo, and must still verify.

    This is the case that made the repo check worth having and also the one
    that could quietly break it: comparing against the directory name passes
    everywhere the two happen to agree.
    """
    calls = fake_openai()
    repo = _foreign_repo(tmp_path, name="repo-signal-worktree")
    (repo / ".mq" / "repo-contract.json").write_text(
        json.dumps({"repo": "repo-signal"}), encoding="utf-8"
    )
    _canonical(repo, repo_name="repo-signal", role="verified in a worktree")

    output = _review(monkeypatch, repo)

    assert "Architecture role: verified in a worktree" in calls[0]
    assert "verified" in output
    assert "repo-mismatch" not in output
