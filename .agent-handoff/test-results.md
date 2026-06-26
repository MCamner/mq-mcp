# Test Results: Gate orchestration-contract staleness on tool-delta, not raw mtime

Status: ready
Author: tester
Created: 2026-06-20
Spec-ref: .agent-handoff/spec.md
Changes-ref: .agent-handoff/changes.md

## Overall verdict

PASS — the false-positive mtime WARN is suppressed and genuine tool-drift still warns; full suite
and PR #15 CI are green.

## Acceptance criteria results

* [x] Newer mtime + unchanged tool set → no staleness WARN — PASS —
  `test_no_warn_when_mtime_newer_but_tool_set_unchanged` (mocks git history to the current tool set;
  asserts no `[WARN]`, asserts "no tool drift" PASS).
* [x] Genuine tool add → staleness WARN naming the tool — PASS —
  `test_warn_when_tool_added_since_contract`.
* [x] Fresh checkout doesn't self-trigger — PASS — covered by the no-delta PASS path; mtime alone
  never warns.
* [x] `validate.yml` + `docs-consistency.yml` stay green — PASS — `gh pr checks 15`: validate pass,
  Docs consistency check pass.

## Tests run

* `uv --directory mq-mcp run pytest ../tests/` — 266 passed (was 264 on main; +2 regression).
* `uv … pytest ../tests/test_orchestration_contract_staleness.py ../tests/test_orchestration_boundary_docs.py` — 6 passed.
* `gh pr checks 15` — validate: pass; Docs consistency check: pass.

## New tests written (if any)

* `tests/test_orchestration_contract_staleness.py::test_no_warn_when_mtime_newer_but_tool_set_unchanged`
* `tests/test_orchestration_contract_staleness.py::test_warn_when_tool_added_since_contract`

## Edge cases / regressions checked

* Removed-tool drift — handled: WARN message now reports `removed:` as well as `added:` (verified by
  reading the branch logic; the added-tool test exercises the symmetric path).
* Git-unavailable path — `_delta_known=False` → PASS-with-note, not WARN (matches spec open-question
  decision). Not independently mocked; covered by code reading.
* Full suite as regression guard — 266 passed, no collateral breakage in other validate_* checks.

## Defects found

None.

## Notes for Reviewer

* Live repo has **genuine** drift (`learn_inbox_draft`, `learn_inbox_drop` added since the contract's
  last commit), so a real run still WARNs correctly — expected, not a defect. Contract refresh is a
  separate follow-up, out of scope for this PR.
* The git-unavailable fallback (PASS-with-note) is verified by reading, not by a dedicated mock —
  low risk, but flag if you want an explicit test added.
