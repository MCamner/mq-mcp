# Review: Gate orchestration-contract staleness on tool-delta, not raw mtime

Status: ready
Author: reviewer
Created: 2026-06-20
Spec-ref: .agent-handoff/spec.md
Changes-ref: .agent-handoff/changes.md
Test-results-ref: .agent-handoff/test-results.md

## Verdict

APPROVE WITH FOLLOW-UPS

The change does exactly what the spec asked: the staleness signal is now gated on a real tool
delta instead of raw mtime, killing the checkout/clone false positive while preserving genuine
drift detection (and improving it — removals are now reported too). The trail is internally
consistent (spec → changes → tests all describe the same behaviour), CI is green on PR #15, and I
verified the core claims against the actual diff and a live run. Two minor, non-blocking follow-ups
keep it from a clean APPROVE.

## Consistency & coverage

* changes.md delivers the spec, and honestly records the one deviation that matters: the real code
  emits `[WARN]`, not `[FAIL]` — implemented against reality. Good.
* test-results.md exercises both directions (no-drift → no WARN; add → WARN). The genuine-add test
  also covers the symmetric removed path indirectly, but there is no dedicated test for the
  git-unavailable PASS-with-note branch (verified by reading only).

## Independent checks performed

* `git diff main...HEAD` read in full — logic confirmed: `_delta_known` defaults False and is set
  True only after a successful `git show` + AST parse; PASS when no delta, PASS-with-note when
  delta unverifiable, WARN only on a real add/remove. Control flow is sound.
* `gh pr checks 15` — validate: pass; Docs consistency check: pass.
* Re-ran the full suite in the worktree: 266 passed.
* Note: MCP `review_diff` / `risk_review_diff` operate on the configured repo's working-tree diff,
  so they could not target this branch (separate worktree) cleanly; reviewed the branch diff
  directly instead.

## MQ merge-bar checks

* Branch off main + Co-Authored-By trailer: ok (commit 8255b73 carries the trailer).
* CI gates green (validate.yml, docs-consistency.yml): ok. No cross-repo contract change → mq-stack-gate not in play.
* No secrets / machine paths; docs & contracts consistent: ok (tool_contracts.json idempotent; no tool added/removed).

## Quality / security notes

* Class A read-only validator; no new attack surface, no new deps. — non-blocking
* Asymmetric tool extraction: `_old_tools` uses a loose `attr.attr == "tool"` match while
  `registered_tools` requires `mcp.tool` specifically. If an old/new server.py ever carried a
  non-`mcp` `.tool` decorator, `_removed_tools` could surface a spurious entry. Pre-existing
  asymmetry (old code shared it for added-tools), now also feeds the removed path. — non-blocking

## Follow-ups (if APPROVE WITH FOLLOW-UPS)

* [ ] Tighten the staleness branch's `_old_tools` extraction to the same `mcp.tool` predicate used
  for `registered_tools`, so added/removed deltas are computed symmetrically.
* [ ] Add a test for the git-unavailable path (`_delta_known=False` → PASS-with-note, never WARN).
* [ ] Separate, already-noted: regenerate `docs/ORCHESTRATION_CONTRACT.md` to clear the genuine
  drift (`learn_inbox_draft`, `learn_inbox_drop`).
