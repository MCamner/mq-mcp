"""
Drift Detector — mq-mcp review engine, Phase 5.

Detects architecture drift between declared documentation and actual runtime state.

Checks:
  1. Tool count — server.py actual count vs README, TOOL_SAFETY.md summary table,
     and tool_contracts.json tool_count field.
  2. Contract coverage — all @mcp.tool() functions present in tool_contracts.json.
  3. Safety doc coverage — all tools mentioned in docs/TOOL_SAFETY.md.
  4. Phantom contracts — tools in tool_contracts.json not found in server.py.
  5. Architecture map freshness — architecture_map.json older than server.py.
  6. RUNTIME_CONTRACT.md existence — RISK if the identity contract is missing.
  7. RUNTIME_CONTRACT.md freshness — NOTE/WARNING if server.py is newer.
  8. Reference document existence — WARNING for each doc listed in the reference
     table of RUNTIME_CONTRACT.md that is missing on disk.

Usage:
  from review_engine.drift_detector import DriftDetector
  detector = DriftDetector()
  findings = detector.detect()
  print(detector.format_report(findings))
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class DriftFinding:
    severity: str   # NOTE, WARNING, RISK
    location: str   # file or component name
    description: str

    def format(self) -> str:
        return f"[{self.severity}] {self.location}\n{self.description}"


class DriftDetector:
    # Docs that must exist per RUNTIME_CONTRACT.md reference table
    _REFERENCE_DOCS: list[str] = [
        "docs/architecture/SYSTEM_OVERVIEW.md",
        "docs/architecture/REVIEW_PIPELINE.md",
        "docs/TOOL_SAFETY.md",
        "docs/tool_contracts.json",
        "TOOL_INDEX.md",
        "ROADMAP.md",
        "SAFETY_MODEL.md",
    ]

    def __init__(self) -> None:
        self._server = REPO_ROOT / "mq-mcp" / "server.py"
        self._contracts = REPO_ROOT / "docs" / "tool_contracts.json"
        self._safety = REPO_ROOT / "docs" / "TOOL_SAFETY.md"
        self._readme = REPO_ROOT / "README.md"
        self._arch_map = REPO_ROOT / "review_engine" / "context" / "architecture_map.json"
        self._runtime_contract = REPO_ROOT / "docs" / "RUNTIME_CONTRACT.md"

    def _server_tools(self) -> list[str]:
        """Extract @mcp.tool() function names from server.py via AST."""
        try:
            tree = ast.parse(self._server.read_text(encoding="utf-8"))
        except Exception:
            return []
        tools: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    attr = dec.func if isinstance(dec, ast.Call) else dec
                    if (
                        isinstance(attr, ast.Attribute)
                        and attr.attr == "tool"
                        and isinstance(attr.value, ast.Name)
                        and attr.value.id == "mcp"
                    ):
                        tools.append(node.name)
        return tools

    def _contracted_tools(self) -> tuple[list[str], int | None]:
        """Return (tool names list, declared tool_count) from tool_contracts.json."""
        try:
            data = json.loads(self._contracts.read_text(encoding="utf-8"))
            names = [t["name"] for t in data.get("tools", []) if "name" in t]
            declared = data.get("tool_count")
            return names, declared
        except Exception:
            return [], None

    def _declared_count_in_file(self, path: Path) -> int | None:
        """Find the first 'N tools' integer in a text file."""
        try:
            text = path.read_text(encoding="utf-8")
            m = re.search(r"\b(\d+)\s+tools?\b", text, re.IGNORECASE)
            return int(m.group(1)) if m else None
        except Exception:
            return None

    def _safety_table_count(self) -> int:
        """Count tool rows in the TOOL_SAFETY.md summary table only."""
        try:
            text = self._safety.read_text(encoding="utf-8")
            # Only count rows in the summary table section at end of file
            m = re.search(r"^## Summary table", text, re.MULTILINE)
            if not m:
                return 0
            summary_section = text[m.start():]
            return len(re.findall(r"^\|\s*`[a-z_]+`", summary_section, re.MULTILINE))
        except Exception:
            return 0

    def detect(self) -> list[DriftFinding]:
        findings: list[DriftFinding] = []

        server_tools = self._server_tools()
        actual = len(server_tools)
        server_set = set(server_tools)

        contracted_names, contracts_declared = self._contracted_tools()
        contracted_set = set(contracted_names)

        # 1 — Tool count: README
        readme_declared = self._declared_count_in_file(self._readme)
        if readme_declared is not None and readme_declared != actual:
            findings.append(DriftFinding(
                severity="WARNING",
                location="README.md",
                description=(
                    f"README declares {readme_declared} tools but server.py has {actual}. "
                    f"Update the count in README.md."
                ),
            ))

        # 2 — Tool count: TOOL_SAFETY.md summary table
        safety_count = self._safety_table_count()
        if safety_count > 0 and safety_count != actual:
            findings.append(DriftFinding(
                severity="WARNING",
                location="docs/TOOL_SAFETY.md",
                description=(
                    f"TOOL_SAFETY.md summary table has {safety_count} entries "
                    f"but server.py has {actual} tools."
                ),
            ))

        # 3 — Tool count: tool_contracts.json tool_count field
        if contracts_declared is not None and contracts_declared != actual:
            findings.append(DriftFinding(
                severity="WARNING",
                location="docs/tool_contracts.json",
                description=(
                    f"tool_contracts.json declares tool_count={contracts_declared} "
                    f"but server.py has {actual} tools."
                ),
            ))

        # 4 — Contract coverage: tools in server.py missing from contracts
        missing = sorted(t for t in server_tools if t not in contracted_set)
        for tool in missing:
            findings.append(DriftFinding(
                severity="WARNING",
                location=f"docs/tool_contracts.json:{tool}",
                description=(
                    f"Tool '{tool}' exists in server.py but has no entry in tool_contracts.json."
                ),
            ))

        # 5 — Phantom contracts: tools in contracts not in server.py
        phantoms = sorted(t for t in contracted_names if t not in server_set)
        for tool in phantoms:
            findings.append(DriftFinding(
                severity="NOTE",
                location=f"docs/tool_contracts.json:{tool}",
                description=(
                    f"Tool '{tool}' is in tool_contracts.json but not found in server.py."
                ),
            ))

        # 6 — Safety doc coverage: tools in server.py not mentioned in TOOL_SAFETY.md
        try:
            safety_text = self._safety.read_text(encoding="utf-8")
            undocumented = [t for t in server_tools if t not in safety_text]
            for tool in undocumented:
                findings.append(DriftFinding(
                    severity="WARNING",
                    location=f"docs/TOOL_SAFETY.md:{tool}",
                    description=(
                        f"Tool '{tool}' in server.py is not mentioned in TOOL_SAFETY.md."
                    ),
                ))
        except Exception:
            pass

        # 7 — Architecture map freshness
        if self._arch_map.exists():
            map_mtime = self._arch_map.stat().st_mtime
            server_mtime = self._server.stat().st_mtime
            if server_mtime > map_mtime:
                hours = (server_mtime - map_mtime) / 3600
                sev = "WARNING" if hours > 24 else "NOTE"
                findings.append(DriftFinding(
                    severity=sev,
                    location="review_engine/context/architecture_map.json",
                    description=(
                        f"architecture_map.json is {hours:.0f}h older than server.py. "
                        f"Run build_repo_context() to refresh."
                    ),
                ))
        else:
            findings.append(DriftFinding(
                severity="WARNING",
                location="review_engine/context/architecture_map.json",
                description="architecture_map.json missing. Run build_repo_context() to generate.",
            ))

        # 8 — RUNTIME_CONTRACT.md existence
        if not self._runtime_contract.exists():
            findings.append(DriftFinding(
                severity="RISK",
                location="docs/RUNTIME_CONTRACT.md",
                description=(
                    "RUNTIME_CONTRACT.md is missing. "
                    "This is the authoritative identity contract for the runtime. "
                    "Create it at docs/RUNTIME_CONTRACT.md."
                ),
            ))
        else:
            # 9 — RUNTIME_CONTRACT.md freshness relative to server.py
            contract_mtime = self._runtime_contract.stat().st_mtime
            server_mtime = self._server.stat().st_mtime
            if server_mtime > contract_mtime:
                hours = (server_mtime - contract_mtime) / 3600
                sev = "WARNING" if hours > 48 else "NOTE"
                findings.append(DriftFinding(
                    severity=sev,
                    location="docs/RUNTIME_CONTRACT.md",
                    description=(
                        f"RUNTIME_CONTRACT.md is {hours:.0f}h older than server.py. "
                        f"Review whether tool model, safety classes, or guarantees need updating."
                    ),
                ))

        # 10 — Reference document existence (docs listed in RUNTIME_CONTRACT.md reference table)
        for rel in self._REFERENCE_DOCS:
            path = REPO_ROOT / rel
            if not path.exists():
                findings.append(DriftFinding(
                    severity="WARNING",
                    location=rel,
                    description=(
                        f"{rel} is listed in the RUNTIME_CONTRACT.md reference table "
                        f"but does not exist on disk."
                    ),
                ))

        return findings

    def format_report(self, findings: list[DriftFinding]) -> str:
        if not findings:
            return "No architecture drift detected."

        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        dist = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))

        lines = [f"Architecture drift: {len(findings)} finding(s)  [{dist}]", ""]
        for f in findings:
            lines.append(f.format())
            lines.append("")
        return "\n".join(lines).rstrip()


if __name__ == "__main__":
    detector = DriftDetector()
    findings = detector.detect()
    print(detector.format_report(findings))
