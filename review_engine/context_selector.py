"""
Context Selector — mq-mcp review engine, Phase 2.

Selects and prioritizes context pieces for injection into review prompts.
Enforces a character budget so injected context never crowds out file content
or the system prompt.

Priority order (lower integer = higher priority):
  1  arch_role      — architecture role string (very short, always include)
  2  past_context   — previous review findings for this file (tailored, high value)
  3  cross_file_ctx — related file roles, symbols, last review (rich but larger)
  99 extra          — any additional context pieces

If total characters exceed budget, lowest-priority pieces are dropped first.
If a single high-priority piece exceeds the remaining budget, it is truncated
rather than dropped — a partial high-value context is better than none.

Usage:
  from review_engine.context_selector import ContextSelector
  cs = ContextSelector()
  cs.add("arch_role", arch_role, priority=1)
  cs.add("past_context", past_context, priority=2)
  cs.add("cross_file_ctx", cross_file_ctx, priority=3)
  selected = cs.selected()
  arch_role     = selected.get("arch_role", "")
  past_context  = selected.get("past_context", "")
  cross_file_ctx = selected.get("cross_file_ctx", "")
"""

from __future__ import annotations

# ~3 000 tokens — leaves room for file content + system prompt + contract
MAX_CONTEXT_CHARS = 12_000


class ContextSelector:
    """Priority-based context selector with a character budget cap.

    Pieces with lower priority integer are included first.
    If a piece fits entirely within the remaining budget, it is included as-is.
    If not, it is truncated to the remaining budget (marked with a truncation note).
    Pieces that cannot fit at all (budget exhausted) are dropped silently.
    """

    def __init__(self, max_chars: int = MAX_CONTEXT_CHARS) -> None:
        self._max = max_chars
        self._pieces: list[tuple[int, str, str]] = []  # (priority, label, content)

    def add(self, label: str, content: str, priority: int = 99) -> None:
        """Register a context piece. Lower priority integer = higher priority."""
        if content and content.strip():
            self._pieces.append((priority, label, content.strip()))

    def selected(self) -> dict[str, str]:
        """Return selected context pieces within budget, highest priority first.

        Drops lowest-priority pieces when budget is exhausted.
        Truncates a piece that partially fits rather than dropping it entirely.
        """
        ordered = sorted(self._pieces, key=lambda x: x[0])
        result: dict[str, str] = {}
        budget = self._max

        for priority, label, content in ordered:
            if budget <= 0:
                break
            if len(content) <= budget:
                result[label] = content
                budget -= len(content)
            else:
                result[label] = content[:budget] + "\n… [context truncated — budget exhausted]"
                budget = 0

        return result
