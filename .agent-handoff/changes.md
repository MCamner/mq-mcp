# Changes: Gate orchestration-contract staleness on tool-delta, not raw mtime

Status: ready
Author: coder
Created: 2026-06-20
Spec-ref: .agent-handoff/spec.md
Branch: fix/orchestration-contract-staleness-tool-delta (off origin/main, clean worktree /tmp/mq-mcp-coder)

## Summary

`validate_orchestration_contract` no longer emits a staleness `[WARN]` from a bare mtime compare.
When `docs/ORCHESTRATION_CONTRACT.md` is older than `server.py`, it now computes the actual tool
delta (added/removed `@mcp.tool` functions since the contract's last commit) and only warns on a
real delta; a newer mtime with an unchanged tool set is a `[PASS]`.

## Files changed

* `mq-mcp/server.py` — `validate_orchestration_contract`, staleness branch (~L2664-2714): replaced
  the always-on `[WARN]` with delta-gated logic. Computes `_added_tools`/`_removed_tools` via the
  existing diff-aware AST extraction; `[PASS]` when no drift, `[PASS]` (with note) when the delta
  can't be verified (git unavailable/shallow checkout), `[WARN]` only on a real add/remove, now
  listing both added and removed tools.
* `tests/test_orchestration_contract_staleness.py` — new regression test (2 cases).

## Deviations from spec

* Spec acceptance criteria referenced `[FAIL]`; the real code emits `[WARN]` (verified at
  server.py:2706 on origin/main). Implemented against reality — the fix gates the `[WARN]`. The
  intent (kill the false positive) is unchanged.
* Added detection of *removed* tools too (spec only named added) — a removal is equally real drift
  and was cheap to include.

## How to verify

* [ ] Newer mtime, unchanged tool set → no staleness WARN —
  `test_no_warn_when_mtime_newer_but_tool_set_unchanged` (mocks git history with the current tool
  set; asserts no `[WARN]`, asserts "no tool drift" PASS).
* [ ] Genuine tool add → staleness WARN naming the tool —
  `test_warn_when_tool_added_since_contract`.
* [ ] Fresh checkout doesn't self-trigger → covered by the no-delta PASS path (mtime alone never warns).
* [ ] CI green: `uv --directory mq-mcp run pytest ../tests/` → 266 passed; `./scripts/validate.sh`,
  `check-tool-contracts.sh`, `check-profiles.py`, `check-stability.py` all OK; `tool_contracts.json`
  idempotent (unchanged).

## Known limitations / follow-ups

* The real repo currently has genuine drift (`learn_inbox_draft`, `learn_inbox_drop` added since the
  contract's last commit), so a live run still correctly WARNs until the contract is regenerated —
  that's expected, not a defect. Follow-up (separate): refresh `ORCHESTRATION_CONTRACT.md`.
* Git-unavailable path intentionally downgrades to PASS-with-note rather than WARN (per spec open
  question) to avoid false positives in detached/shallow checkouts.

## Pre-flight checks run

* [ ] Lint: ruff not installed in env — skipped (not in this repo's local toolchain).
* [x] Byte-compile: `python -m py_compile mq-mcp/server.py` OK.
* [x] Tests: full suite 266 passed (was 264; +2 regression).
* [x] CI-gate scripts: validate.sh / check-tool-contracts.sh / check-profiles.py /
  check-stability.py all OK; tool_contracts.json idempotent.
* [ ] Committed: not committed — working in clean worktree, awaiting go for commit/PR.
