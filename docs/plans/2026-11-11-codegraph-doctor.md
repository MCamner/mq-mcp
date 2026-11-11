# CodeGraph Doctor Implementation Plan

## Goal

Expose read-only CodeGraph version, index freshness and daemon handshake diagnostics in doctor.

## Owner repo

mq-mcp

## Secondary repos

None.

## Architecture boundary

mq-mcp owns local CLI diagnostics; CodeGraph owns indexing and daemon lifecycle. No cross-repo contracts change.

## Non-goals

Automatic installation, indexing, daemon startup or repair.

## Approval gates

- Before file writes: no, implementation requested by user.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: yes.

## Test gates

`uv --directory mq-mcp run pytest ../tests/test_codegraph_health.py ../tests/test_cli.py -q`
`uv --directory mq-mcp run python main.py doctor --json`

## Rollback

Revert only the new diagnostics module, tests and doctor/README additions.

### Task 1: Implement optional diagnostics

Files: create `mq-mcp/codegraph_health.py`, `tests/test_codegraph_health.py`; modify `mq-mcp/main.py`, `tests/test_cli.py`, `README.md`.

1. Add failing tests for unavailable CLI, invalid/failed/timed-out commands, stale index, daemon handshake and permission errors.
2. Use bounded subprocesses with JSON status and a bounded Unix-socket hello read.
3. Integrate optional JSON and text output without changing required readiness or exit codes.
4. Run focused tests and live doctor; inspect diff. No commit requested.
