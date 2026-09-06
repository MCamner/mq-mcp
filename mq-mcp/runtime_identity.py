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

#: Distinguishes "look it up" from a caller that deliberately supplied None,
#: which is what an uninstalled runtime legitimately has.
_UNSET = object()

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


def installation_metadata() -> dict[str, Any] | None:
    """PEP 610 installation metadata, when this runtime was installed at all.

    mq-mcp normally runs from a checkout and is not a distribution, so this is
    normally None. That is a fact about the runtime, not a failure.
    """
    try:
        raw = distribution(COMPONENT).read_text("direct_url.json")
    except (PackageNotFoundError, OSError, ValueError):
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
    commit = vcs_info.get("commit_id")
    return commit if isinstance(commit, str) and commit else None


def head_commit(root: Path) -> str | None:
    """The commit the checkout is on. Never a tag, never a remote ref."""
    return _probe(root, "rev-parse", "--verify", "HEAD")


def declared_version(root: Path) -> str | None:
    """The version this code declares, from the checkout it lives in.

    Falls back to installed distribution metadata, which is what a built
    artifact carries instead of a `VERSION` file.
    """
    try:
        declared = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        declared = ""
    if declared:
        return declared
    try:
        return distribution(COMPONENT).version or None
    except (PackageNotFoundError, ValueError):
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
    metadata = installation_metadata() if direct_url is _UNSET else direct_url

    install_type, source = install_source(metadata)
    version = declared_version(checkout)
    commit = recorded_commit(metadata) or head_commit(checkout)

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
