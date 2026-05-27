"""
Convention Extractor — mq-mcp review engine, v1.2.0.

Extracts generalizable coding conventions from review findings and persists
them into architecture_memory/decisions/ as convention entries.

Conventions differ from one-off review findings: they are rules that apply
across multiple files in the codebase, not just the file that was reviewed.

Example convention:
  CONVENTION: MCP tools that call the OpenAI API must check for OPENAI_API_KEY
              before constructing the client.
  AREA: server, review_engine
  RATIONALE: Several reviews flagged missing API key checks — this is a
             consistent pre-condition across all AI-powered tools.

Usage:
  from review_engine.convention_extractor import ConventionExtractor
  extractor = ConventionExtractor(client, model)
  conventions = extractor.extract(
      file_path="mq-mcp/server.py",
      findings_text=raw_review_output,
      existing_titles=["MCP tools must declare a safety class"],
  )
  for c in conventions:
      print(c["convention"], c["area"], c["rationale"])
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


EXTRACT_SYSTEM = """\
You are a coding convention extractor. You read review findings for a specific
file and identify generalizable coding conventions for this codebase.

A convention is a rule that:
- Applies to multiple files, not just the one being reviewed
- Can be stated as a clear, actionable rule ("always X", "never Y", "X must Y")
- Is inferred from one or more findings — not invented

Output format — one block per convention, no blank lines between fields:
CONVENTION: <one-sentence rule>
AREA: <comma-separated keywords matching file paths where this applies>
RATIONALE: <one sentence — why this rule exists, based on the findings>

Allowed AREA keywords: server, bridge, review_engine, safety, mcp, paths,
git, observability, tests, contracts, architecture, tool, subprocess, api.

Rules:
- Max 5 conventions per extraction.
- Skip conventions that duplicate the existing list shown below.
- If no generalizable conventions can be inferred, output exactly:
  No conventions found.
- No preamble. No closing remarks.\
"""

EXTRACT_USER = """\
Extract coding conventions from these review findings.

File reviewed: {file_path}

{existing_block}

## Findings

{findings_text}\
"""


@dataclass
class Convention:
    convention: str
    area: str
    rationale: str


class ConventionExtractor:
    """Extracts coding conventions from review findings via a single model call."""

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def extract(
        self,
        file_path: str,
        findings_text: str,
        existing_titles: list[str] | None = None,
    ) -> list[Convention]:
        """Run extraction. Returns a (possibly empty) list of Convention objects."""
        if not findings_text.strip():
            return []

        existing_titles = existing_titles or []
        if existing_titles:
            existing_block = "## Existing conventions (do not duplicate)\n\n" + "\n".join(
                f"- {t}" for t in existing_titles
            )
        else:
            existing_block = ""

        user = EXTRACT_USER.format(
            file_path=file_path,
            existing_block=existing_block,
            findings_text=findings_text.strip(),
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": user},
            ],
            max_tokens=800,
        )
        raw = (response.choices[0].message.content or "").strip()

        if raw.lower().startswith("no conventions found"):
            return []

        return _parse_conventions(raw)


# ── parser ────────────────────────────────────────────────────────────────────

_CONV_RE = re.compile(
    r"CONVENTION:\s*(.+?)\s*\n"
    r"AREA:\s*(.+?)\s*\n"
    r"RATIONALE:\s*(.+?)(?=\nCONVENTION:|\Z)",
    re.DOTALL,
)


def _parse_conventions(text: str) -> list[Convention]:
    results: list[Convention] = []
    for m in _CONV_RE.finditer(text):
        conv = m.group(1).strip()
        area = m.group(2).strip()
        rationale = m.group(3).strip()
        if conv and area:
            results.append(Convention(convention=conv, area=area, rationale=rationale))
    return results
