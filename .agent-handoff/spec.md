# Spec: Gate orchestration-contract staleness on tool-delta, not raw mtime

Status: ready
Author: planner
Created: 2026-06-20
Repo: mq-mcp
Issue: none (sourced from systems/mq-mcp blocker list)

## Goal

`validate_orchestration_contract` should only warn that `docs/ORCHESTRATION_CONTRACT.md` is stale
when the contract is *actually* behind the tool surface — i.e. when server.py has registered or
removed `@mcp.tool` functions the contract doesn't reflect. Today a bare mtime comparison
(`contract_mtime < server_mtime`) fires on any clone/checkout or unrelated touch of server.py,
producing false staleness FAILs and eroding trust in the deterministic readiness signal.

## Scope

In scope:
* Change the staleness check in `validate_orchestration_contract` so a FAIL requires a real
  semantic delta (tools added/removed vs the contract's last-committed server.py), reusing the
  existing diff-aware tool-extraction that already runs there.
* When mtime is newer but the tool set is unchanged, downgrade to an informational note (or no
  finding), not a FAIL.

Out of scope:
* The parallel mtime checks in `review_engine/drift_detector.py` (architecture_map / RUNTIME_CONTRACT).
* Any change to the contract document format or to other validate_* checks.

## Acceptance criteria

* [ ] With server.py mtime newer than the contract but **no** tool added/removed since the
  contract's last commit, `validate_orchestration_contract` does NOT emit a `[FAIL]` for staleness.
* [ ] With a tool genuinely added to server.py and not in the contract, it still emits the existing
  staleness FAIL listing the new tool(s).
* [ ] A fresh `git checkout` (which rewrites mtimes) does not by itself trigger a staleness FAIL.
* [ ] `docs-consistency.yml` and `validate.yml` stay green.

## Affected files / areas

* `mq-mcp/server.py` — `validate_orchestration_contract`, staleness branch around L2658-2700:
  make the `[FAIL]` conditional on the computed `_new_tools` (and removed tools) being non-empty.

## Constraints

* Keep the check deterministic and offline-safe — git calls already wrapped in try/except with
  timeouts; preserve that fallback behaviour if git is unavailable.
* No new dependencies; stdlib + existing `_ast`/`subprocess` usage only.
* Don't weaken the genuine "contract missing a tool" detection — only suppress the pure-mtime
  false positive.

## GitHub / CI target

* Branch off `main`: `fix/orchestration-contract-staleness-tool-delta`
* Lands as: PR to main
* CI gates that must pass: `validate.yml`, `docs-consistency.yml`

## Open questions for Coder

* When git is unavailable (no commit found for the contract), should the check fall back to the old
  mtime FAIL or stay silent? Recommend: informational note, not FAIL, to avoid false positives in
  detached/shallow checkouts. Document the decision in changes.md.

## Notes

* Source: `systems/mq-mcp/index` + agent-view blocker "validate_orchestration_contract varnar om
  contract är äldre än server.py". Verified against code at server.py:2666-2668.
* This file was produced as a **test run of the handoff-planner skill** in mq-mcp; delete if not
  pursuing the fix.
