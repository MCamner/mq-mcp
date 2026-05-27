"""
Multi-Pass Reviewer — mq-mcp review engine, Phase 4.

Pass 1 — Structure analysis: compact structural summary of the file.
          No findings. Output is context for subsequent passes.
Pass 2 — Review pass: contract-driven review enriched with structure context.
Pass 3 — Consistency pass: checks doc vs runtime divergence (docstrings,
          names, type hints vs actual implementation behavior).
Pass 4 — Deduplication: merges Pass 2 + Pass 3 findings, keeps highest
          severity per location, drops near-duplicate bodies, re-sorts.

Usage:
  from review_engine.multi_pass_reviewer import MultiPassReviewer
  reviewer = MultiPassReviewer(client, model)
  result = reviewer.run(
      file_path=relative_path,
      file_content=content,
      contract=contract_text,
      arch_role=arch_role_string,
      skill_content=skill_text,
      skill_name=skill_name,
      past_context=past_findings_text,
  )
  print(result.output)     # formatted, deduplicated findings
  print(result.pass_count) # 3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STRUCTURE_PASS_SYSTEM = """\
You are a code structure analyst preparing context for a code reviewer.
Do NOT produce review findings. Do NOT judge code quality.

Produce a compact structural summary covering:

**Responsibility:** What this file does (1-2 sentences).
**Key patterns:** Naming conventions, error handling style, module structure visible in the code.
**Hotspots:** The 2-3 functions or sections with the most complexity or edge cases.
**Review focus:** What areas the reviewer should prioritize given the structure.

Rules:
- Under 200 words total.
- No findings. No quality judgments.
- Output only the summary — no preamble, no closing remarks.\
"""

STRUCTURE_PASS_USER = """\
Produce a structural summary for this file.

File: {file_path}{role_line}

```
{file_content}
```\
"""

CONSISTENCY_PASS_SYSTEM = """\
You are a consistency reviewer. Your only job is to identify places where
a file's documentation, comments, type hints, or function names diverge from
its actual implementation.

Output ONLY findings where there is a real doc vs runtime mismatch.
Do NOT re-flag issues a standard comment reviewer would catch (style, missing
docstrings, naming preferences). Focus solely on inconsistency.

Output format — identical to the comment review contract:
[SEVERITY] file:line
One sentence describing the inconsistency.

Allowed severity labels:
- NOTE: cosmetic drift (minor mismatch, low-stakes)
- WARNING: documented behavior the code does not implement, or vice versa
- RISK: undocumented behavior that could mislead callers or hide bugs

Rules:
- Max 10 findings. Only flag real inconsistencies.
- If there are no inconsistencies, output exactly: No consistency issues found.
- No preamble. No closing remarks.\
"""

CONSISTENCY_PASS_USER = """\
Check this file for doc vs implementation inconsistencies.

File: {file_path}{role_line}

## Structure analysis

{structure_summary}

```
{file_content}
```\
"""


@dataclass
class PassResult:
    structure_summary: str
    output: str
    findings: list[Any] = field(default_factory=list)
    pass_count: int = 2


class MultiPassReviewer:
    """Runs a multi-pass review pipeline using the OpenAI chat API."""

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def _call(self, system: str, user: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    def structure_pass(
        self,
        file_path: str,
        file_content: str,
        arch_role: str = "",
    ) -> str:
        """Pass 1 — structural analysis. Returns a compact summary string."""
        role_line = f"\nArchitecture role: {arch_role}" if arch_role else ""
        user = STRUCTURE_PASS_USER.format(
            file_path=file_path,
            role_line=role_line,
            file_content=file_content,
        )
        return self._call(STRUCTURE_PASS_SYSTEM, user, max_tokens=400)

    def review_pass(
        self,
        file_path: str,
        file_content: str,
        contract: str,
        arch_role: str = "",
        skill_content: str = "",
        skill_name: str = "",
        past_context: str = "",
        structure_summary: str = "",
    ) -> str:
        """Pass 2 — contract-driven review enriched with structure context."""
        skill_section = (
            f"\n\n## Skill: {skill_name}\n\n{skill_content}"
            if skill_content
            else ""
        )
        system = (
            "You are a code review engine operating under a strict review contract.\n"
            "Follow the contract exactly. Do not deviate from the output format.\n"
            "Do not modify code. Output only structured review findings.\n\n"
            f"{contract}{skill_section}"
        )

        role_line = f"\nArchitecture role: {arch_role}" if arch_role else ""
        past_section = (
            f"\n\n## Previous review context\n\n{past_context}" if past_context else ""
        )
        structure_section = (
            f"\n\n## Structure analysis\n\n{structure_summary}" if structure_summary else ""
        )
        user = (
            f"Review this file under the contract above.\n\n"
            f"File: {file_path}{role_line}{structure_section}{past_section}\n\n"
            f"```\n{file_content}\n```"
        )
        return self._call(system, user, max_tokens=2048)

    def consistency_pass(
        self,
        file_path: str,
        file_content: str,
        arch_role: str = "",
        structure_summary: str = "",
    ) -> str:
        """Pass 3 — doc vs runtime consistency. Returns findings in standard format."""
        role_line = f"\nArchitecture role: {arch_role}" if arch_role else ""
        user = CONSISTENCY_PASS_USER.format(
            file_path=file_path,
            role_line=role_line,
            structure_summary=structure_summary,
            file_content=file_content,
        )
        return self._call(CONSISTENCY_PASS_SYSTEM, user, max_tokens=1024)

    def _deduplicate(self, findings: list[Any]) -> list[Any]:
        """Pass 4 — merge findings from multiple passes.

        Per location: keeps the highest-severity finding.
        Across all findings: drops entries whose body starts the same as an
        already-kept finding (case-insensitive, first 50 chars).
        """
        from review_engine.severity_engine import SEVERITY_ORDER

        order: dict[Any, int] = {s: i for i, s in enumerate(SEVERITY_ORDER)}

        # Per location: keep highest severity
        by_location: dict[str, Any] = {}
        for f in findings:
            if f.location not in by_location:
                by_location[f.location] = f
            else:
                existing = by_location[f.location]
                if order.get(f.severity, 99) < order.get(existing.severity, 99):
                    by_location[f.location] = f

        # Drop near-duplicate bodies
        seen: set[str] = set()
        result: list[Any] = []
        for f in sorted(
            by_location.values(),
            key=lambda f: (order.get(f.severity, 99), f.line or 0),
        ):
            key = f.body[:50].lower().strip()
            if key not in seen:
                seen.add(key)
                result.append(f)

        return result

    def run(
        self,
        file_path: str,
        file_content: str,
        contract: str,
        arch_role: str = "",
        skill_content: str = "",
        skill_name: str = "",
        past_context: str = "",
    ) -> PassResult:
        """Run all passes. Returns a PassResult with formatted, deduplicated output."""
        from review_engine.severity_engine import parse_findings, format_summary

        # Pass 1 — structure analysis
        structure_summary = self.structure_pass(file_path, file_content, arch_role)

        # Pass 2 — main contract review
        raw_review = self.review_pass(
            file_path=file_path,
            file_content=file_content,
            contract=contract,
            arch_role=arch_role,
            skill_content=skill_content,
            skill_name=skill_name,
            past_context=past_context,
            structure_summary=structure_summary,
        )

        # Pass 3 — consistency check
        consistency_raw = self.consistency_pass(
            file_path=file_path,
            file_content=file_content,
            arch_role=arch_role,
            structure_summary=structure_summary,
        )

        # Pass 4 — deduplicate across passes
        review_findings = parse_findings(raw_review)
        consistency_findings = parse_findings(consistency_raw)
        all_findings = self._deduplicate(review_findings + consistency_findings)

        output = format_summary(all_findings, file_path) if all_findings else raw_review

        return PassResult(
            structure_summary=structure_summary,
            output=output,
            findings=all_findings,
            pass_count=3,
        )
