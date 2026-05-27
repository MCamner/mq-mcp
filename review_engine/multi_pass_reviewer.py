"""
Multi-Pass Reviewer — mq-mcp review engine, Phase 4.

Runs a two-pass review pipeline:
  Pass 1 — Structure analysis: produces a compact structural summary of the
            file used as context for Pass 2. Not a review. No findings.
  Pass 2 — Review pass: the main contract-driven review, enriched with the
            structure summary from Pass 1.

This produces higher-quality findings by giving the model explicit structural
grounding before it starts reviewing — it knows what the file is before it
decides what to flag.

Usage:
  from review_engine.multi_pass_reviewer import MultiPassReviewer
  reviewer = MultiPassReviewer(client, model)
  output, findings = reviewer.run(
      file_path=relative_path,
      file_content=content,
      contract=contract_text,
      arch_role=arch_role_string,
      skill_content=skill_text,
      past_context=past_findings_text,
  )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import openai

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


@dataclass
class PassResult:
    structure_summary: str
    raw_review: str
    pass_count: int


class MultiPassReviewer:
    """Runs a two-pass review pipeline using the OpenAI chat API."""

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
            f"\n\n## Previous review context\n\n{past_context}"
            if past_context
            else ""
        )
        structure_section = (
            f"\n\n## Structure analysis\n\n{structure_summary}"
            if structure_summary
            else ""
        )

        user = (
            f"Review this file under the contract above.\n\n"
            f"File: {file_path}{role_line}{structure_section}{past_section}\n\n"
            f"```\n{file_content}\n```"
        )

        return self._call(system, user, max_tokens=2048)

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
        """Run Pass 1 then Pass 2. Returns a PassResult with both outputs."""
        structure_summary = self.structure_pass(file_path, file_content, arch_role)

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

        return PassResult(
            structure_summary=structure_summary,
            raw_review=raw_review,
            pass_count=2,
        )
