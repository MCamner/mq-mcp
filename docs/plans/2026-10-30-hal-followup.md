# HAL follow-up Implementation Plan

## Goal

Correct HEAD CI reporting, finish repo-status-json integration, and register missing local repos.

## Owner repo

mq-hal (status and reports); mq-mcp (tool documentation and local registration).

## Secondary repos

macos-scripts, mqobsidian, atlas-core: registration only.

## Architecture boundary

HAL owns report collection. MCP delegates through its existing allowlist. No runtime logic moves between repos.

## Non-goals

No release, deployment, commit, push, or PR publication.

## Approval gates

- Before file writes: no, requested fixes are authorized.
- Before commit: yes.
- Before push/merge: yes.
- Before deletion/settings changes: no deletion; only requested local repo registration.

## Tasks

1. mq-hal: add regression tests for HEAD filtering, reruns, empty CI, and empty stderr. Fix scripts/ci_status.py, scripts/brief.py, scripts/repo_status_json.py. Add syntax gate entry, command reference, changelog, and local settings ignore.
2. mq-mcp: document repo-status-json in README, demo, safety and generated contracts; update local .env registration for existing repo roots.

## Test gates

- python3 -m pytest /tmp/mq-hal-followup/tests -q (mocked subprocess regressions before/after fix).
- mq-hal: bash tests/repo-status-json-smoke.sh; bash tests/ci-status-smoke.sh; bash tests/brief-smoke.sh; bash tests/docs-smoke.sh.
- mq-mcp: python3 scripts/generate_tool_contracts.py; bash scripts/check-mcp-tool-docs.sh; bash scripts/check-integration-docs.sh.
- git diff --check in both repos.

## Rollback

Restore only this task's file hunks; remove new tests/plan if unwanted. Restore only MQ_MCP_LOCAL_REPOS in the ignored .env, preserving other settings.
