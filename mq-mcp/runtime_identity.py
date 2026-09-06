"""What this mq-mcp process is, decided once at start and never revised.

`mq.runtime-identity.v1` is mq-agent's contract; this module is a producer of
it, and deliberately shares no code with the consumer. The contract crosses the
repository boundary. The implementation does not.

The one property worth stating plainly: **the identity is captured at import,
not at request time.** `_version()` in `server.py` reads `VERSION` from disk on
every call, which is right for a health check and wrong here. A process started
from commit A, still running after the checkout moved to B, would answer B —
reporting the working tree rather than itself, and hiding exactly the drift the
consumer exists to detect. The endpoint that is supposed to expose that gap
would be the thing concealing it.

So capture happens once and returns a plain value. What the checkout does
afterwards is the checkout's business.

Identity is component + version + commit. An identity that cannot be completed
is recorded as `partial` or `unknown`; it is never filled in from the latest
tag, `origin/main`, the working directory, or a neighbouring repository. A
missing commit is a weaker identity, not a gap to be closed with a guess.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

#: The contract this module produces. Owned by mq-agent; vendored as a test
#: fixture here, never imported.
SCHEMA_ID = "mq.runtime-identity.v1"

#: The component this module speaks for, and only this one.
COMPONENT = "mq-mcp"

#: The directory the running code was imported from, and the checkout above it.
APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent

#: The file this module was loaded from — the subject every claim is checked
#: against. A directory is a neighbourhood; a file is a thing.
MODULE_FILE = Path(__file__).resolve()

#: Distinguishes "look it up" from a caller that deliberately supplied None,
#: which is what an uninstalled runtime legitimately has.
_UNSET = object()

#: What this contract accepts as a commit. PEP 610 covers version control
#: systems whose revisions are not hex SHAs; a revision the contract cannot
#: express is absent rather than coerced into the field.
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")

#: Seconds a git probe may take. Identity is observability: a probe that hangs
#: would delay process start, and a probe that fails is simply an unknown.
PROBE_TIMEOUT = 5


def _probe(root: Path, *args: str) -> str | None:
    """Stdout of a git command, or None if it could not be run or failed."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _within(child: Path, parent: Path) -> bool:
    try:
        return child == parent or child.is_relative_to(parent)
    except (OSError, ValueError):
        return False


def describes_imported_code(
    metadata: Any, subject: Path, owned_files: set[Path] | None
) -> bool:
    """Whether an installed distribution may speak for the code that was
    imported.

    `distribution("mq-mcp")` finds a distribution by *name*, and a name is not
    a subject. A virtualenv can hold an installed mq-mcp while the running
    module was loaded from a checkout somewhere else; believing that
    distribution would freeze a well-formed, schema-valid identity naming code
    this process never ran. Nothing downstream could detect it, because nothing
    about the record would look wrong.

    Ownership is therefore the distribution's own file list, not the directory
    it sits in. A site-packages holds every distribution in the environment, so
    "the imported module is under the install root" proves only that the two
    are neighbours. `RECORD` names what this distribution actually installed.

    An editable install is the exception with its own evidence: it records the
    directory it points at, and the imported file has to be inside it.
    """
    if isinstance(metadata, dict):
        dir_info = metadata.get("dir_info")
        if isinstance(dir_info, dict) and dir_info.get("editable") is True:
            raw_url = metadata.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                return False
            recorded = unquote(urlparse(raw_url).path)
            return bool(recorded) and _within(subject, Path(recorded))
    return owned_files is not None and subject in owned_files


def _installed_files(dist: Any) -> set[Path] | None:
    """What this distribution installed, resolved. None when it cannot say."""
    try:
        entries = dist.files
    except Exception:
        return None
    if not entries:
        return None
    owned: set[Path] = set()
    for entry in entries:
        try:
            owned.add(Path(str(dist.locate_file(entry))).resolve())
        except (OSError, ValueError):
            continue
    return owned or None


def _direct_url_of(dist: Any) -> dict[str, Any] | None:
    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, ValueError):
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def bound_distribution(subject: Path | None = None) -> tuple[Any, dict[str, Any] | None] | None:
    """The installed distribution that owns the imported code, if any.

    mq-mcp normally runs from a checkout and is not a distribution, so this is
    normally None. That is a fact about the runtime, not a failure — and it is
    also the answer when a distribution merely shares the name.

    Everything drawn from installation metadata — commit, version, install
    type — comes through here, so nothing can be bound for one field and
    unbound for another.
    """
    target = subject or MODULE_FILE
    try:
        dist = distribution(COMPONENT)
    except (PackageNotFoundError, OSError, ValueError):
        return None
    metadata = _direct_url_of(dist)
    if not describes_imported_code(metadata, target, _installed_files(dist)):
        return None
    return dist, metadata


def install_source(metadata: Any) -> tuple[str, str | None]:
    """How this runtime was installed, and the checkout behind it.

    PEP 610 decides, never the shape of a path: a directory that merely looks
    like a checkout proves nothing. `dir_info` without `editable: true` is a
    directory copied into site-packages, which is not an editable install, and
    `archive_info` covers source archives as well as wheels — so the URL has to
    end in `.whl` before this claims one.

    A runtime that was never installed is `unknown`. The enum has no `source`,
    and adding one would fork a contract this repository does not own.
    """
    if not isinstance(metadata, dict):
        return "unknown", None
    raw_url = metadata.get("url")
    url = raw_url if isinstance(raw_url, str) else ""

    dir_info = metadata.get("dir_info")
    if isinstance(dir_info, dict):
        if dir_info.get("editable") is not True:
            return "unknown", None
        path = unquote(urlparse(url).path) if url else ""
        return ("editable", path) if path else ("unknown", None)

    if "archive_info" in metadata:
        return ("wheel", None) if urlparse(url).path.endswith(".whl") else ("unknown", None)

    return "unknown", None


def recorded_commit(metadata: Any) -> str | None:
    """The commit a build records about itself, per PEP 610.

    Outranks the working tree: it says what this code was made from, while the
    checkout says only what is there now.
    """
    if not isinstance(metadata, dict):
        return None
    vcs_info = metadata.get("vcs_info")
    if not isinstance(vcs_info, dict):
        return None
    return usable_commit(vcs_info.get("commit_id"))


def usable_commit(value: Any) -> str | None:
    """A commit this contract can carry, or None."""
    return value if isinstance(value, str) and _COMMIT.match(value) else None


def head_commit(root: Path) -> str | None:
    """The commit the checkout is on. Never a tag, never a remote ref."""
    return usable_commit(_probe(root, "rev-parse", "--verify", "HEAD"))


def declared_version(root: Path, dist: Any = None) -> str | None:
    """The version this code declares, from the checkout it lives in.

    Falls back to the *bound* distribution — the one shown to own the imported
    module — which is what a built artifact carries instead of a `VERSION`
    file. Never to a distribution that merely shares the name: that would put a
    stranger's version beside this checkout's commit, and the result would be
    valid, plausible and false.
    """
    try:
        declared = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        declared = ""
    if declared:
        return declared
    if dist is None:
        return None
    try:
        return dist.version or None
    except (AttributeError, ValueError):
        return None


def identity_quality(version: str | None, commit: str | None) -> str:
    """How complete the identity is — derived, never asserted.

    Mechanical on purpose: the contract constrains these three cases, so a
    record that claimed more than it carried would fail validation rather than
    travel.
    """
    if version and commit:
        return "verified"
    if version:
        return "partial"
    return "unknown"


def capture(root: Path | str | None = None, *, direct_url: Any = _UNSET) -> dict[str, Any]:
    """Observe this runtime once and return the result as a plain value.

    Called at import, so the returned dict is what the process reports for the
    rest of its life. Nothing here reads anything again later.
    """
    checkout = Path(root) if root is not None else REPO_ROOT
    subject = MODULE_FILE if root is None else Path(checkout)
    if direct_url is _UNSET:
        bound = bound_distribution(subject)
        dist, metadata = bound if bound is not None else (None, None)
    else:
        # Supplied without any evidence of what was installed, so only the
        # editable form — which records its own directory — can tie itself.
        dist = None
        metadata = direct_url if describes_imported_code(direct_url, subject, None) else None

    install_type, source = install_source(metadata)
    version = declared_version(checkout, dist)
    commit = recorded_commit(metadata) or head_commit(checkout)

    # The contract has three levels and none of them is "a commit but no
    # version": `unknown` requires both to be null. A readable HEAD beside an
    # unreadable version is a real observation with nowhere to go, so the
    # identity degrades. The record is what travels, and a record a consumer
    # must reject carries less than one that says little.
    if version is None:
        commit = None

    return {
        "schema": SCHEMA_ID,
        "component": COMPONENT,
        "version": version,
        "commit": commit,
        "install_type": install_type,
        "identity_quality": identity_quality(version, commit),
        "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "executable": sys.executable or None,
        "module_path": str(APP_ROOT),
        "source_path": source or (str(checkout) if (checkout / ".git").exists() else None),
    }


#: Taken once, at process start. Everything after this reads the snapshot.
IDENTITY: dict[str, Any] = capture()


def identity() -> dict[str, Any]:
    """This process's identity. A copy, so no caller can edit the record."""
    return dict(IDENTITY)
