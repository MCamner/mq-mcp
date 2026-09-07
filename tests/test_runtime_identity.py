"""mq-mcp reports what it is, once, and does not revise it.

The point of the snapshot is narrow and easy to lose: a process that reads
`VERSION` and `git rev-parse HEAD` when the request arrives reports the
checkout, not itself. After the checkout moves, a process started from commit A
would answer B — which is the drift mq-agent's runtime provenance exists to
catch, produced by the very endpoint meant to expose it.

So the tests here are mostly one test asked twice: the identity is a value
taken at start, not a view onto the working tree. Once at the function level,
once across a real process boundary, because a module-level constant and a
running server are not the same claim.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mq-mcp" / "runtime_identity.py"
SERVER_PATH = ROOT / "mq-mcp" / "server.py"
SCHEMA_PATH = ROOT / "tests" / "fixtures" / "mq-agent-schemas" / "runtime_identity.schema.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("mq_mcp_runtime_identity_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def identity_module():
    return _load_module()


@pytest.fixture
def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A real repository with a VERSION file and one commit."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    (root / "VERSION").write_text("2.0.2\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "A")
    return root


def _req(host: str | None = "127.0.0.1:8765", path: str = "/runtime-identity"):
    headers = {} if host is None else {"host": host}
    return SimpleNamespace(headers=headers, url=SimpleNamespace(path=path))


# --- the contract ---------------------------------------------------------


def test_the_captured_identity_satisfies_the_contract(identity_module, validator, checkout):
    validator.validate(identity_module.capture(checkout))


def test_this_runtime_reports_itself_against_the_contract(identity_module, validator):
    validator.validate(identity_module.identity())


def test_the_component_is_named_and_the_schema_is_declared(identity_module, checkout):
    captured = identity_module.capture(checkout)

    assert captured["schema"] == "mq.runtime-identity.v1"
    assert captured["component"] == "mq-mcp"


# --- the identity is a value, not a view ----------------------------------


def test_a_moving_checkout_does_not_move_the_captured_commit(identity_module, checkout):
    first = _git(checkout, "rev-parse", "HEAD")
    captured = identity_module.capture(checkout)
    assert captured["commit"] == first

    (checkout / "moved").write_text("b", encoding="utf-8")
    _git(checkout, "add", "-A")
    _git(checkout, "commit", "-q", "-m", "B")
    second = _git(checkout, "rev-parse", "HEAD")
    assert second != first

    assert captured["commit"] == first


def test_a_rewritten_version_file_does_not_rewrite_the_captured_version(
    identity_module, checkout
):
    captured = identity_module.capture(checkout)
    assert captured["version"] == "2.0.2"

    (checkout / "VERSION").write_text("9.9.9\n", encoding="utf-8")

    assert captured["version"] == "2.0.2"


def test_a_process_still_reports_the_commit_it_started_from(tmp_path):
    """The claim that matters, made where it is actually made.

    Not `capture(root)` held in a variable — a dict of strings obviously does
    not change. This starts a process against a *copy* of this repository, so
    the module resolves its own `REPO_ROOT` and freezes `IDENTITY` at import,
    exactly as the server does. Then the checkout moves under it.
    """
    repo = tmp_path / "mq-mcp"
    (repo / "mq-mcp").mkdir(parents=True)
    (repo / "mq-mcp" / "runtime_identity.py").write_text(
        MODULE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / "VERSION").write_text("2.0.2\n", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "A")
    started = _git(repo, "rev-parse", "HEAD")

    # No root argument anywhere: the module decides for itself, at import.
    script = textwrap.dedent(
        """
        import importlib.util, json, sys
        spec = importlib.util.spec_from_file_location("ri", sys.argv[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(json.dumps(module.identity()), flush=True)
        for _ in sys.stdin:
            print(json.dumps(module.identity()), flush=True)
        """
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(repo / "mq-mcp" / "runtime_identity.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        at_start = json.loads(process.stdout.readline())
        assert at_start["commit"] == started
        assert at_start["version"] == "2.0.2"

        # The checkout moves under the running process.
        (repo / "moved").write_text("b", encoding="utf-8")
        (repo / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "B")
        moved_to = _git(repo, "rev-parse", "HEAD")
        assert moved_to != started

        process.stdin.write("ask\n")
        process.stdin.flush()
        after = json.loads(process.stdout.readline())
    finally:
        process.stdin.close()
        process.terminate()
        process.wait(timeout=10)

    assert after["commit"] == started, "the process reported a commit it never ran"
    assert after["commit"] != moved_to
    assert after["version"] == "2.0.2", "the process adopted a version written after it started"


# --- an identity that cannot be completed is never filled in --------------


def test_a_checkout_without_git_reports_a_version_and_no_commit(identity_module, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "VERSION").write_text("2.0.2\n", encoding="utf-8")

    captured = identity_module.capture(plain)

    assert captured["version"] == "2.0.2"
    assert captured["commit"] is None
    assert captured["identity_quality"] == "partial"


def test_a_runtime_that_can_say_nothing_says_nothing(identity_module, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    captured = identity_module.capture(empty)

    assert captured["version"] is None
    assert captured["commit"] is None
    assert captured["identity_quality"] == "unknown"


def test_the_commit_is_head_and_never_the_latest_tag(identity_module, checkout):
    """A tag is a different observation. It is never a source for this one."""
    _git(checkout, "tag", "-a", "v1.0.0", "-m", "old")
    tagged = _git(checkout, "rev-parse", "HEAD")
    (checkout / "later").write_text("x", encoding="utf-8")
    _git(checkout, "add", "-A")
    _git(checkout, "commit", "-q", "-m", "after the tag")
    head = _git(checkout, "rev-parse", "HEAD")

    captured = identity_module.capture(checkout)

    assert captured["commit"] == head
    assert captured["commit"] != tagged


def test_a_dirty_worktree_is_not_this_contract_s_business(identity_module, checkout):
    """Identity says which commit the code came from. Cleanliness is mq-agent's
    question, and answering it here would be a second, quieter definition."""
    head = _git(checkout, "rev-parse", "HEAD")
    (checkout / "VERSION").write_text("2.0.3\n", encoding="utf-8")

    captured = identity_module.capture(checkout)

    assert captured["commit"] == head
    assert "worktree_clean" not in captured


@pytest.mark.parametrize(
    ("version", "commit", "expected"),
    [
        ("2.0.2", "a" * 40, "verified"),
        ("2.0.2", None, "partial"),
        (None, None, "unknown"),
    ],
)
def test_quality_is_derived_from_what_is_carried(identity_module, version, commit, expected):
    assert identity_module.identity_quality(version, commit) == expected


# --- how it was installed is a separate question --------------------------


def test_an_uninstallable_runtime_is_unknown_rather_than_guessed(identity_module):
    """mq-mcp runs from a checkout and is not a distribution. `unknown` is the
    honest answer: the enum has no `source`, and inventing one would fork a
    contract this repo does not own."""
    assert identity_module.install_source(None) == ("unknown", None)


@pytest.mark.parametrize(
    ("direct_url", "expected"),
    [
        ({"url": "file:///x/mq-mcp", "dir_info": {"editable": True}}, "editable"),
        ({"url": "file:///x/mq-mcp", "dir_info": {}}, "unknown"),
        ({"url": "https://x/mq_mcp-2.0.2-py3-none-any.whl", "archive_info": {}}, "wheel"),
        ({"url": "https://x/mq_mcp-2.0.2.tar.gz", "archive_info": {}}, "unknown"),
        ("not a mapping", "unknown"),
    ],
)
def test_install_type_follows_pep_610_and_never_the_path(identity_module, direct_url, expected):
    assert identity_module.install_source(direct_url)[0] == expected


def test_installed_metadata_never_speaks_for_code_it_cannot_be_shown_to_own(
    identity_module, checkout
):
    """The dangerous case, because the result would look perfectly valid.

    `distribution("mq-mcp")` finds a distribution by *name*. Nothing says it is
    the copy this process imported: a venv can hold an installed mq-mcp while
    the running module was loaded from a checkout somewhere else. Believing its
    commit would freeze a well-formed, schema-valid identity naming code this
    process never ran — a lie no consumer could detect.
    """
    head = _git(checkout, "rev-parse", "HEAD")
    someone_elses = "b" * 40

    captured = identity_module.capture(
        checkout,
        direct_url={"url": "file:///elsewhere", "vcs_info": {"vcs": "git", "commit_id": someone_elses}},
    )

    assert captured["commit"] == head
    assert captured["commit"] != someone_elses


_WHEEL = {"url": "https://x/mq_mcp-2.0.2-py3-none-any.whl", "archive_info": {}}
_EDITABLE_HERE = {"url": "file:///src/mq-mcp", "dir_info": {"editable": True}}
_EDITABLE_ELSEWHERE = {"url": "file:///src/other", "dir_info": {"editable": True}}
_SITE = "/venv/lib/site-packages"


@pytest.mark.parametrize(
    ("metadata", "subject", "owned", "expected"),
    [
        # An editable install records the directory it points at; the imported
        # module has to be inside it.
        (_EDITABLE_HERE, "/src/mq-mcp/mq-mcp/runtime_identity.py", None, True),
        (_EDITABLE_ELSEWHERE, "/src/mq-mcp/mq-mcp/runtime_identity.py", None, False),
        # Everything else must appear in the distribution's own file list.
        (_WHEEL, f"{_SITE}/mq_mcp/runtime_identity.py", [f"{_SITE}/mq_mcp/runtime_identity.py"], True),
        # Sharing a site-packages is not ownership. This is the case that looks
        # owned and is not: same directory, different distribution.
        (_WHEEL, f"{_SITE}/mq_mcp_b/runtime_identity.py", [f"{_SITE}/mq_mcp_a/runtime_identity.py"], False),
        # A distribution that cannot list its files proves nothing.
        (_WHEEL, f"{_SITE}/mq_mcp/runtime_identity.py", None, False),
        # A wheel from an index carries no direct_url at all; the file list
        # still settles ownership.
        (None, f"{_SITE}/mq_mcp/runtime_identity.py", [f"{_SITE}/mq_mcp/runtime_identity.py"], True),
        (None, f"{_SITE}/mq_mcp/runtime_identity.py", None, False),
    ],
)
def test_ownership_is_the_file_list_and_never_the_neighbourhood(
    identity_module, metadata, subject, owned, expected
):
    assert (
        identity_module.describes_imported_code(
            metadata,
            Path(subject),
            {Path(f) for f in owned} if owned is not None else None,
        )
        is expected
    )


def test_a_version_is_never_borrowed_from_a_stranger(identity_module, monkeypatch, tmp_path):
    """The second half of the same rule, and the one I left open.

    Commit metadata is tied to the imported code. The version fallback was not,
    so a checkout with no VERSION beside an unrelated installed mq-mcp would
    report that stranger's version next to this checkout's commit — valid,
    plausible, and false.
    """
    root = tmp_path / "no-version"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    (root / "code").write_text("x", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "A")

    class _Stranger:
        version = "9.9.9"
        files = ()

        def locate_file(self, name):
            return Path("/somewhere/else") / str(name)

        def read_text(self, name):
            return None

    monkeypatch.setattr(identity_module, "distribution", lambda _name: _Stranger())

    captured = identity_module.capture(root)

    assert captured["version"] != "9.9.9"
    assert captured["version"] is None
    assert captured["identity_quality"] == "unknown"


def test_the_version_fallback_needs_a_distribution_that_owns_this_code(
    identity_module, tmp_path
):
    """A bound distribution may supply the version a built artifact has no
    VERSION file for. An unbound one may not, and there is no third case."""
    root = tmp_path / "artifact"
    root.mkdir()

    class _Owner:
        version = "2.0.2"

    assert identity_module.declared_version(root, None) is None
    assert identity_module.declared_version(root, _Owner()) == "2.0.2"


def test_a_checkout_keeps_its_own_install_type_out_of_a_stranger_s_metadata(
    identity_module, checkout
):
    """An editable record pointing somewhere else does not make this editable."""
    captured = identity_module.capture(
        checkout,
        direct_url={"url": "file:///elsewhere", "dir_info": {"editable": True}},
    )

    assert captured["install_type"] == "unknown"
    assert captured["source_path"] == str(checkout)


# --- a record that cannot be valid is not sent ----------------------------


def test_a_commit_without_a_version_degrades_instead_of_going_invalid(
    identity_module, validator, tmp_path
):
    """A readable HEAD beside an unreadable version is a real observation, and
    the contract has no level for it: `unknown` requires both to be null. The
    record is what travels, so the identity degrades rather than shipping
    something a consumer would reject."""
    root = tmp_path / "versionless"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    (root / "code").write_text("x", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "A")
    assert _git(root, "rev-parse", "HEAD")

    captured = identity_module.capture(root)

    validator.validate(captured)
    assert captured["identity_quality"] == "unknown"
    assert captured["version"] is None
    assert captured["commit"] is None


@pytest.mark.parametrize(
    "recorded", ["not-a-sha", "X" * 40, "abc", "ABCDEF1", "", "abcdef1\n", " abcdef1"]
)
def test_a_commit_that_is_not_a_git_sha_is_not_a_commit(identity_module, recorded):
    """PEP 610 covers more version control systems than git; this contract's
    `commit` is a git object name. A revision it cannot express is absent, not
    coerced — and the check is exact, since `$` also matches before a trailing
    newline."""
    assert identity_module.usable_commit(recorded) is None


@pytest.mark.parametrize(
    ("vcs", "revision"),
    [
        # Seven characters, all valid hex, and not a commit. A pattern cannot
        # tell an svn revision from an abbreviated SHA; only the recorded
        # system can, so the system is what gets checked.
        ("svn", "1234567"),
        ("svn", "deadbee"),
        ("bzr", "abcdef1"),
        ("hg", "a" * 40),
        (None, "abcdef1"),
    ],
)
def test_only_git_records_a_commit_this_contract_can_carry(
    identity_module, vcs, revision
):
    assert (
        identity_module.recorded_commit(
            {"url": "x", "vcs_info": {"vcs": vcs, "commit_id": revision}}
        )
        is None
    )


def test_a_git_object_name_still_passes_through(identity_module):
    """A rule that only ever says no is not a rule."""
    assert (
        identity_module.recorded_commit(
            {"url": "x", "vcs_info": {"vcs": "git", "commit_id": "b" * 40}}
        )
        == "b" * 40
    )


# --- the route ------------------------------------------------------------


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("mq_mcp_server_runtime_identity", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.anyio
async def test_the_route_answers_with_the_contract(server, validator):
    response = await server.runtime_identity(_req())

    validator.validate(json.loads(response.body))


@pytest.mark.anyio
async def test_the_route_rejects_a_foreign_host(server):
    """Same boundary as every other observability route: a rebinding page
    carries its own Host and gets a 403, not a runtime fingerprint."""
    response = await server.runtime_identity(_req(host="evil.com"))

    assert response.status_code == 403


@pytest.mark.anyio
async def test_the_route_serves_the_snapshot_and_observes_nothing(server, monkeypatch):
    """If the request path can still observe, the freeze is decoration."""
    monkeypatch.setattr(
        server._runtime_identity,
        "capture",
        lambda *a, **k: pytest.fail("the route re-observed the checkout"),
    )

    response = await server.runtime_identity(_req())

    assert json.loads(response.body)["component"] == "mq-mcp"


# --- the boundary ---------------------------------------------------------


def test_the_producer_does_not_import_mq_agent():
    """The contract crosses the repository boundary; the implementation does not."""
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "mq_agent" not in source
    assert "import mq-agent" not in source


def test_the_producer_imports_with_mq_agent_absent(identity_module):
    """A grep proves the text. Running it with the package hidden proves the fact."""
    script = textwrap.dedent(
        f"""
        import importlib.util, json, sys

        class Blocked:
            def find_module(self, name, path=None):
                if name.startswith("mq_agent"):
                    raise AssertionError("imported mq_agent")

        sys.meta_path.insert(0, Blocked())
        spec = importlib.util.spec_from_file_location("ri", {str(MODULE_PATH)!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(json.dumps(module.identity()))
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["component"] == "mq-mcp"


def test_the_producer_decides_nothing():
    """No comparison, no reason code, no policy. Phase 4a produces one fact."""
    source = MODULE_PATH.read_text(encoding="utf-8")

    for owned_elsewhere in ("RTP0", "matches_checkout", "blocked", "status"):
        assert owned_elsewhere not in source
