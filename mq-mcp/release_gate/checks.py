"""Deterministic Release Gate v2 checks."""
from __future__ import annotations

import io
import json
import re
import subprocess
import tokenize
from pathlib import Path

from .models import GateCheck


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def check_tests_pass(repo: Path, test_command: list[str] | None = None) -> GateCheck:
    if not test_command:
        return GateCheck(
            name="tests_pass",
            status="warning",
            message="Tests were not run for this gate invocation.",
            next_action="Run Release Gate v2 with a test command before release.",
        )
    try:
        result = subprocess.run(
            test_command,
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        return GateCheck(
            name="tests_pass",
            status="blocked",
            message=f"Test command failed to run: {exc}",
            blocker=True,
            next_action="Fix the test command and rerun tests.",
        )
    if result.returncode == 0:
        return GateCheck("tests_pass", "pass", "Tests passed.")
    return GateCheck(
        name="tests_pass",
        status="blocked",
        message="Tests failed.",
        blocker=True,
        next_action="Fix failing tests and rerun Release Gate v2.",
    )


def check_lint_type_quality(repo: Path, lint_command: list[str] | None = None) -> GateCheck:
    """Run an optional lint/type command and report repo quality readiness.

    Mirrors check_tests_pass: a warning when no command is supplied (the gate
    cannot vouch for quality it did not run), pass on a clean exit, blocked on a
    non-zero exit. Deterministic — no quality tooling is assumed or installed.
    """
    if not lint_command:
        return GateCheck(
            name="lint_type_quality",
            status="warning",
            message="Lint/type checks were not run for this gate invocation.",
            next_action="Run Release Gate v2 with a lint command (e.g. 'ruff check . && mypy .') before release.",
        )
    try:
        result = subprocess.run(
            lint_command,
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        return GateCheck(
            name="lint_type_quality",
            status="blocked",
            message=f"Lint/type command failed to run: {exc}",
            blocker=True,
            next_action="Fix the lint/type command and rerun.",
        )
    if result.returncode == 0:
        return GateCheck("lint_type_quality", "pass", "Lint/type checks passed.")
    return GateCheck(
        name="lint_type_quality",
        status="blocked",
        message="Lint/type checks failed.",
        blocker=True,
        next_action="Fix lint/type findings and rerun Release Gate v2.",
    )


def check_version_consistent(repo: Path, target: str) -> GateCheck:
    version = target.removeprefix("v")
    version_file = repo / "VERSION"
    pyproject = repo / "pyproject.toml"
    values: list[str] = []
    if version_file.is_file():
        values.append(version_file.read_text(encoding="utf-8").strip().removeprefix("v"))
    if pyproject.is_file():
        text = _read(pyproject)
        if f'version = "{version}"' in text or f"version = '{version}'" in text:
            values.append(version)
    if not values:
        return GateCheck(
            "version_consistent",
            "blocked",
            f"No VERSION or pyproject version found for {target}.",
            blocker=True,
            next_action="Add or sync release version metadata.",
        )
    if all(value == version for value in values):
        return GateCheck("version_consistent", "pass", f"Version metadata matches {target}.")
    return GateCheck(
        "version_consistent",
        "blocked",
        f"Version metadata does not match {target}.",
        blocker=True,
        next_action="Sync VERSION and pyproject.toml with the target version.",
    )


def check_file_mentions_target(repo: Path, filename: str, target: str, blocker: bool) -> GateCheck:
    path = repo / filename
    name = filename.lower().replace(".", "_")
    if not path.is_file():
        return GateCheck(
            name=name,
            status="blocked" if blocker else "warning",
            message=f"{filename} is missing.",
            blocker=blocker,
            next_action=f"Add {filename} before release.",
        )
    text = _read(path)
    if target in text or target.removeprefix("v") in text:
        return GateCheck(name, "pass", f"{filename} mentions {target}.")
    return GateCheck(
        name=name,
        status="blocked" if blocker else "warning",
        message=f"{filename} does not mention {target}.",
        blocker=blocker,
        next_action=f"Update {filename} for {target}.",
    )


def _repo_exposes_mcp_tools(repo: Path) -> bool:
    server_candidates = [
        repo / "mq-mcp" / "server.py",
        repo / "server.py",
    ]
    for path in server_candidates:
        text = _read(path)
        if "@mcp.tool" in text or "FastMCP" in text:
            return True
    return False


def check_contracts_valid(repo: Path) -> GateCheck:
    candidates = [repo / "docs" / "tool_contracts.json", repo / "contracts" / "release_gate_v2.schema.json"]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        if not _repo_exposes_mcp_tools(repo):
            return GateCheck(
                "contracts_valid",
                "warning",
                "No release/tool contract schema was found; non-MCP repo contract validation was skipped.",
                next_action="Add contracts/release_gate_v2.schema.json if this repo participates in Release Gate v2.",
            )
        return GateCheck(
            "contracts_valid",
            "blocked",
            "No release/tool contract schema was found.",
            blocker=True,
            next_action="Add docs/tool_contracts.json or contracts/release_gate_v2.schema.json.",
        )
    for path in existing:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return GateCheck(
                "contracts_valid",
                "blocked",
                f"Invalid JSON contract: {path.relative_to(repo)} ({exc})",
                blocker=True,
                next_action="Fix invalid contract JSON.",
            )
    return GateCheck("contracts_valid", "pass", "Contract JSON files are valid.")


def check_safety_classes_valid(repo: Path) -> GateCheck:
    path = repo / "docs" / "tool_contracts.json"
    if not path.is_file():
        if not _repo_exposes_mcp_tools(repo):
            return GateCheck(
                "safety_classes_valid",
                "pass",
                "No MCP server detected; tool safety class check skipped.",
            )
        return GateCheck(
            "safety_classes_valid",
            "warning",
            "docs/tool_contracts.json is not present; no tool safety classes checked.",
            next_action="Add tool safety contract metadata if this repo exposes tools.",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return GateCheck("safety_classes_valid", "blocked", f"Cannot parse tool contracts: {exc}", True, "Fix tool_contracts.json.")
    tools = data.get("tools", [])
    missing = [str(tool.get("name", "<unnamed>")) for tool in tools if not (tool.get("class") or tool.get("safety_class"))]
    if missing:
        return GateCheck(
            "safety_classes_valid",
            "blocked",
            f"Tools missing safety class: {', '.join(missing[:5])}",
            blocker=True,
            next_action="Add safety class metadata for every tool.",
        )
    return GateCheck("safety_classes_valid", "pass", "Tool safety classes are present.")


def check_learn_contract_valid(repo: Path) -> GateCheck:
    if not (repo / "mq-mcp" / "server.py").is_file():
        return GateCheck(
            "learn_contract_valid",
            "pass",
            "No mq-mcp server detected; learn contract check skipped.",
        )

    required = [
        repo / "docs" / "LEARNING_CONTRACT.md",
        repo / "docs" / "LEARNING_MODEL.md",
        repo / "schemas" / "learning.schema.json",
    ]
    missing = [str(path.relative_to(repo)) for path in required if not path.is_file()]
    if missing:
        return GateCheck(
            "learn_contract_valid",
            "blocked",
            f"Learn contract files are missing: {', '.join(missing)}.",
            blocker=True,
            next_action="Restore learning contract docs and schema before release.",
        )

    try:
        schema = json.loads((repo / "schemas" / "learning.schema.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return GateCheck(
            "learn_contract_valid",
            "blocked",
            f"Learning schema is invalid JSON: {exc}",
            blocker=True,
            next_action="Fix schemas/learning.schema.json.",
        )

    required_schema_keys = {"$schema", "type", "required", "properties"}
    missing_keys = sorted(required_schema_keys - set(schema))
    if missing_keys:
        return GateCheck(
            "learn_contract_valid",
            "blocked",
            f"Learning schema missing keys: {', '.join(missing_keys)}.",
            blocker=True,
            next_action="Restore the learning schema contract shape.",
        )
    return GateCheck("learn_contract_valid", "pass", "Learn contract docs and schema are valid.")


def check_learn_alias_tools_present(repo: Path) -> GateCheck:
    server = repo / "mq-mcp" / "server.py"
    contracts = repo / "docs" / "tool_contracts.json"
    aliases = ("learn_status", "search_learned_patterns", "explain_learned_pattern")

    if not server.is_file():
        return GateCheck(
            "learn_alias_tools_present",
            "pass",
            "No mq-mcp server detected; learn alias check skipped.",
        )

    if not contracts.is_file():
        return GateCheck(
            "learn_alias_tools_present",
            "blocked",
            "server.py or docs/tool_contracts.json is missing.",
            blocker=True,
            next_action="Restore server and tool contract metadata before release.",
        )

    server_text = server.read_text(encoding="utf-8", errors="replace")
    missing_server = [name for name in aliases if f"def {name}" not in server_text]
    try:
        data = json.loads(contracts.read_text(encoding="utf-8"))
    except Exception as exc:
        return GateCheck(
            "learn_alias_tools_present",
            "blocked",
            f"Cannot parse tool contracts: {exc}",
            blocker=True,
            next_action="Fix docs/tool_contracts.json.",
        )
    tools = {str(tool.get("name")): tool for tool in data.get("tools", []) if isinstance(tool, dict)}
    missing_contracts = [name for name in aliases if name not in tools]
    unsafe_aliases = [
        name
        for name in aliases
        if name in tools and (tools[name].get("class") != "A" or tools[name].get("write") is not False)
    ]

    problems = []
    if missing_server:
        problems.append(f"missing server aliases: {', '.join(missing_server)}")
    if missing_contracts:
        problems.append(f"missing contract aliases: {', '.join(missing_contracts)}")
    if unsafe_aliases:
        problems.append(f"aliases not Class A/read-only: {', '.join(unsafe_aliases)}")
    if problems:
        return GateCheck(
            "learn_alias_tools_present",
            "blocked",
            f"Learn alias tools are not release-ready: {'; '.join(problems)}.",
            blocker=True,
            next_action="Restore mq-agent learn compatibility aliases and regenerate tool contracts.",
        )
    return GateCheck("learn_alias_tools_present", "pass", "mq-agent learn compatibility aliases are present and read-only.")


def check_learn_hygiene_pass(repo: Path) -> GateCheck:
    try:
        import learn_engine
    except Exception as exc:
        return GateCheck(
            "learn_hygiene_pass",
            "warning",
            f"Learn hygiene could not be checked: {exc}",
            next_action="Fix learn_engine importability and rerun Release Gate v2.",
        )

    report = learn_engine.hygiene_report(repo)
    message = (
        f"Learn hygiene {report['status']}: "
        f"records={report['records']}, "
        f"duplicates={len(report['duplicates'])}, "
        f"invalid={len(report['invalid_records'])}, "
        f"low_confidence={len(report['low_confidence_stored'])}, "
        f"missing_validation={len(report['missing_validation'])}."
    )

    if report["status"] == "pass":
        return GateCheck("learn_hygiene_pass", "pass", message)
    if report["status"] == "warning":
        return GateCheck(
            "learn_hygiene_pass",
            "warning",
            message,
            next_action="Review duplicate or incomplete learn records before release.",
        )
    return GateCheck(
        "learn_hygiene_pass",
        "blocked",
        message,
        blocker=True,
        next_action="Fix invalid or unsafe low-confidence learn records before release.",
    )


def check_perception_artifacts_valid(repo: Path) -> GateCheck:
    candidates = _find_perception_artifacts(repo)
    if not candidates:
        return GateCheck(
            "perception_artifacts_valid",
            "pass",
            "No perception artifacts found; nothing to validate.",
        )

    invalid: list[str] = []
    for path in candidates:
        errors = _validate_perception_artifact(path)
        if errors:
            invalid.append(f"{path.relative_to(repo)} ({'; '.join(errors)})")

    if not invalid:
        return GateCheck(
            "perception_artifacts_valid",
            "pass",
            f"Validated {len(candidates)} perception artifact(s).",
        )
    return GateCheck(
        "perception_artifacts_valid",
        "blocked",
        f"Invalid perception artifact(s): {', '.join(invalid[:3])}",
        blocker=True,
        next_action="Fix perception JSON artifacts before release.",
    )


def _find_perception_artifacts(repo: Path) -> list[Path]:
    patterns = [
        "perception/**/*.json",
        "reports/perception/**/*.json",
        "reports/perception*.json",
        "docs/perception/**/*.json",
        "docs/perception*.json",
        "tests/fixtures/*perception*.json",
    ]
    found: dict[Path, None] = {}
    for pattern in patterns:
        for path in repo.glob(pattern):
            if path.is_file():
                found[path] = None
    return sorted(found)


def _validate_perception_artifact(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    if not isinstance(payload, dict):
        return ["artifact must be a JSON object"]

    required = ["source_type", "source_path", "ocr_text", "visual_summary", "risk_signals", "confidence"]
    errors = [f"missing {key}" for key in required if key not in payload]
    if payload.get("source_type") not in {"screenshot", "diagram", "ui", "terminal", "browser"}:
        errors.append(f"invalid source_type: {payload.get('source_type')}")
    if payload.get("confidence") not in {"low", "medium", "high"}:
        errors.append(f"invalid confidence: {payload.get('confidence')}")
    if "risk_signals" in payload and not isinstance(payload["risk_signals"], list):
        errors.append("risk_signals must be a list")
    if "detected_regions" in payload and not isinstance(payload["detected_regions"], list):
        errors.append("detected_regions must be a list")
    return errors


def check_repo_signal_readiness_export(repo: Path) -> GateCheck:
    exports_dir = repo / ".repo-signal" / "exports"
    if not exports_dir.is_dir():
        return GateCheck(
            "repo_signal_readiness_export",
            "warning",
            ".repo-signal/exports/ not found; repo-signal readiness export was not checked.",
            next_action="Run `repo-signal export` before final release.",
        )

    expected = {
        "callgraph.json": "callgraph.v1",
        "symbol_index.json": "symbol_index.v1",
        "repo_summary.json": "repo_summary.v1",
        "risk_map.json": "risk_map.v1",
    }
    missing: list[str] = []
    invalid: list[str] = []
    for filename, schema in expected.items():
        path = exports_dir / filename
        if not path.is_file():
            missing.append(filename)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            invalid.append(f"{filename} unreadable ({exc})")
            continue
        actual_schema = payload.get("schema") if isinstance(payload, dict) else None
        if actual_schema != schema:
            invalid.append(f"{filename} schema {actual_schema!r}, expected {schema!r}")

    if invalid:
        return GateCheck(
            "repo_signal_readiness_export",
            "blocked",
            f"Invalid repo-signal readiness export: {', '.join(invalid[:3])}",
            blocker=True,
            next_action="Regenerate repo-signal exports and rerun Release Gate v2.",
        )
    if missing:
        return GateCheck(
            "repo_signal_readiness_export",
            "warning",
            f"repo-signal readiness export is incomplete: missing {', '.join(missing)}.",
            next_action="Run `repo-signal export` before final release.",
        )
    return GateCheck(
        "repo_signal_readiness_export",
        "pass",
        "repo-signal readiness export packs are present and schema-valid.",
    )


def check_release_notes_present(repo: Path, target: str) -> GateCheck:
    release_notes = repo / "docs" / "RELEASE_NOTES.md"
    changelog = repo / "CHANGELOG.md"
    version = target.removeprefix("v")
    release_text = _read(release_notes)
    changelog_text = _read(changelog)
    if (
        release_notes.is_file()
        and (target in release_text or version in release_text)
    ) or (
        changelog.is_file()
        and (target in changelog_text or version in changelog_text)
    ):
        return GateCheck("release_notes_present", "pass", f"Release notes mention {target}.")
    return GateCheck(
        "release_notes_present",
        "blocked",
        f"Release notes for {target} are missing.",
        blocker=True,
        next_action="Add release notes or a CHANGELOG entry for the target.",
    )


def check_perception_review(repo: Path) -> GateCheck:
    """Read-only review of mq-image-analyze perception output.

    Schema validation lives in check_perception_artifacts_valid. This check is
    the read-only *review*: it reads valid perception artifacts and surfaces the
    risk signals mq-image-analyze flagged, so they are visible before release. It
    never mutates anything and never blocks — perception risk is advisory input,
    not a deterministic release blocker.
    """
    candidates = _find_perception_artifacts(repo)
    if not candidates:
        return GateCheck(
            "perception_review",
            "pass",
            "No perception artifacts found; nothing to review.",
        )

    signals: list[str] = []
    for path in candidates:
        if _validate_perception_artifact(path):
            continue  # invalid artifacts are already reported by the validity check
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for signal in payload.get("risk_signals", []) or []:
            signals.append(f"{path.relative_to(repo)}: {signal}")

    if not signals:
        return GateCheck(
            "perception_review",
            "pass",
            f"Reviewed {len(candidates)} perception artifact(s); no risk signals reported.",
        )
    return GateCheck(
        "perception_review",
        "warning",
        f"Perception review surfaced {len(signals)} risk signal(s): {'; '.join(signals[:3])}",
        next_action="Review mq-image-analyze risk signals before release.",
    )


def check_contract_drift(repo: Path) -> GateCheck:
    """Detect tool-contract drift between the MCP server and tool_contracts.json.

    Drift means the runtime exposes a different number of @mcp.tool() functions
    than docs/tool_contracts.json declares — a release blocker, because callers
    and safety docs would describe a surface that no longer matches the runtime.
    Skips repos that do not expose MCP tools.
    """
    server = None
    for candidate in (repo / "mq-mcp" / "server.py", repo / "server.py"):
        if candidate.is_file():
            server = candidate
            break
    if server is None:
        return GateCheck("contract_drift", "pass", "No MCP server detected; contract drift check skipped.")

    server_text = server.read_text(encoding="utf-8", errors="replace")
    decorator_count = len(re.findall(r"@mcp\.tool\(", server_text))
    if decorator_count == 0:
        return GateCheck("contract_drift", "pass", "No @mcp.tool() definitions found; contract drift check skipped.")

    contracts = repo / "docs" / "tool_contracts.json"
    if not contracts.is_file():
        return GateCheck(
            "contract_drift",
            "blocked",
            "Runtime exposes MCP tools but docs/tool_contracts.json is missing.",
            blocker=True,
            next_action="Generate docs/tool_contracts.json with scripts/generate_tool_contracts.py.",
        )
    try:
        contract_count = len(json.loads(contracts.read_text(encoding="utf-8")).get("tools", []))
    except Exception as exc:
        return GateCheck(
            "contract_drift",
            "blocked",
            f"Cannot parse docs/tool_contracts.json: {exc}",
            blocker=True,
            next_action="Fix docs/tool_contracts.json.",
        )
    if decorator_count != contract_count:
        return GateCheck(
            "contract_drift",
            "blocked",
            f"Tool contract drift: server.py defines {decorator_count} @mcp.tool() functions "
            f"but docs/tool_contracts.json declares {contract_count}.",
            blocker=True,
            next_action="Regenerate tool contracts so they match the runtime tool count.",
        )
    return GateCheck(
        "contract_drift",
        "pass",
        f"No tool contract drift: {decorator_count} tools in server and contracts.",
    )


def _blank_string_literals(source: str) -> str:
    """Blank the content of Python string literals, preserving line structure.

    Line-based pattern scans must not match dangerous tokens that only appear
    inside string literals — for example the security-pattern *definitions* in
    server.py. tokenize handles raw, multi-line, and adjacent strings correctly;
    falls back to the original source if tokenization fails.
    """
    try:
        chars = [list(line) for line in source.splitlines(keepends=True)]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type != tokenize.STRING:
                continue
            (srow, scol), (erow, ecol) = tok.start, tok.end
            for row in range(srow, erow + 1):
                idx = row - 1
                if idx >= len(chars):
                    continue
                start = scol if row == srow else 0
                end = ecol if row == erow else len(chars[idx])
                for col in range(start, min(end, len(chars[idx]))):
                    if chars[idx][col] not in "\r\n":
                        chars[idx][col] = " "
        return "".join("".join(line) for line in chars)
    except Exception:
        return source


_UNSAFE_COMMAND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"os\.system\s*\("), "os.system()"),
    (re.compile(r"os\.popen\s*\("), "os.popen()"),
    (re.compile(r"shell\s*=\s*True"), "subprocess shell=True"),
    (re.compile(r"\beval\s*\("), "eval()"),
    (re.compile(r"\bexec\s*\("), "exec()"),
]


def check_unsafe_commands(repo: Path) -> GateCheck:
    """Detect ungated unsafe command execution in the tool-exposed surface.

    Scans the MCP server and bridge entrypoints for shell/eval/exec patterns.
    String-literal content is blanked first so pattern *definitions* do not
    match, and a line may be explicitly exempted with a trailing `# nosec`
    comment for audited, gated calls. Any remaining match is a release blocker.
    """
    sources = [
        repo / "mq-mcp" / "server.py",
        repo / "server.py",
        repo / "mq-mcp" / "bridge.py",
        repo / "bridge.py",
    ]
    existing = [path for path in sources if path.is_file()]
    if not existing:
        return GateCheck("unsafe_commands", "pass", "No MCP server/bridge surface detected; unsafe command check skipped.")

    findings: list[str] = []
    for path in existing:
        text = path.read_text(encoding="utf-8", errors="replace")
        blanked = _blank_string_literals(text).splitlines()
        raw = text.splitlines()
        for lineno, line in enumerate(blanked, start=1):
            original = raw[lineno - 1] if lineno - 1 < len(raw) else ""
            if original.rstrip().endswith("# nosec"):
                continue
            for pattern, label in _UNSAFE_COMMAND_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(repo)}:{lineno} {label}")
                    break

    if not findings:
        return GateCheck(
            "unsafe_commands",
            "pass",
            f"No ungated unsafe command execution found in {len(existing)} entrypoint file(s).",
        )
    return GateCheck(
        "unsafe_commands",
        "blocked",
        f"Ungated unsafe command execution: {', '.join(findings[:3])}",
        blocker=True,
        next_action="Gate or remove unsafe command execution, or mark an audited line with `# nosec`.",
    )


def run_p0_checks(
    repo: Path,
    target: str,
    test_command: list[str] | None = None,
    lint_command: list[str] | None = None,
) -> list[GateCheck]:
    return [
        check_tests_pass(repo, test_command),
        check_lint_type_quality(repo, lint_command),
        check_version_consistent(repo, target),
        check_file_mentions_target(repo, "CHANGELOG.md", target, blocker=True),
        check_file_mentions_target(repo, "README.md", target, blocker=False),
        check_file_mentions_target(repo, "ROADMAP.md", target, blocker=False),
        check_contracts_valid(repo),
        check_safety_classes_valid(repo),
        check_contract_drift(repo),
        check_unsafe_commands(repo),
        check_learn_contract_valid(repo),
        check_learn_alias_tools_present(repo),
        check_learn_hygiene_pass(repo),
        check_perception_artifacts_valid(repo),
        check_perception_review(repo),
        check_repo_signal_readiness_export(repo),
        check_release_notes_present(repo, target),
    ]
