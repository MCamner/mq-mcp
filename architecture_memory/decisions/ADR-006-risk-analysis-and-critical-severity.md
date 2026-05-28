---
id: ADR-006
title: Risk analysis tools use a grep pre-scan before API calls, and CRITICAL severity is reserved for risk modes
status: accepted
category: decisions
area: review_engine risk_review_file risk_review_diff severity_engine
---

## Decision

The risk analysis tools (`risk_review_file`, `risk_review_diff`) run a
deterministic grep-based pre-scan (`_detect_security_patterns`) before any
OpenAI API call. The pre-scan results are injected as context into the prompt.

`CRITICAL` severity is added above `RISK` in the severity ordering and is
exclusively used by risk-mode contracts (`risk-review.md`, `security-review.md`).
It must not appear in `comment-review.md` or `architecture-review.md` output.

## Rationale

Pre-scan before API call:
- Eliminates cost of calling the API for files with obvious structural issues
- Provides ground truth to the model rather than relying on it to re-discover
  known patterns from scratch
- Makes the pre-scan results falsifiable and auditable without an API key

CRITICAL above RISK:
- `RISK` was already the highest severity before v1.7.0
- Findings that represent immediate exploitable vulnerabilities (curl|bash, 
  direct code execution paths) need a distinct label so callers can gate
  on them separately
- Keeping CRITICAL out of comment/architecture modes prevents severity label
  inflation in non-security contexts

## String literal stripping in pre-scan

The pre-scan strips string literal content from each line before pattern
matching. This prevents false positives from files that define or document
the dangerous patterns (e.g., a security utility that mentions `os.system()`
in a description string).

## Consequences

- `review_runtime_contract` may warn that CRITICAL is not present in the
  architecture review severity table — this is expected. CRITICAL is only
  for risk modes.
- `_detect_security_patterns` must be maintained alongside `_SECURITY_PATTERNS`
  and `_SHELL_PATTERNS`. Adding a new pattern requires updating both the
  regex list and the security skill (`reviews/skills/security-review.md`).
- The pre-scan does not replace the AI review — it adds context. A clean
  pre-scan does not mean the file is safe.
