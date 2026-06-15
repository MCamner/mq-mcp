# Release Gate v2

Release Gate v2 is the deterministic release-readiness contract for the MQ
stack.

It answers four questions:

```text
Can this repo be released safely right now?
What blocks release?
What is only a warning?
What should be fixed first?
```

## Ownership

```text
mq-agent orchestrates workflows and renders operator output.
mq-mcp owns Release Gate v2 rules, blocker/warning logic and JSON output.
repo-signal provides repo readiness signals.
mq-image-analyze provides perception output.
```

mq-agent must not duplicate Release Gate v2 rules locally.

## Status

| Status | Meaning |
| ------ | ------- |
| `pass` | Ready to release |
| `warning` | Releasable, but should be cleaned up |
| `blocked` | Do not release |

## P0 Checks

The first gate includes only these checks:

```text
tests_pass
lint_type_quality
version_consistent
changelog_updated
readme_current
roadmap_current
contracts_valid
safety_classes_valid
contract_drift
unsafe_commands
learn_contract_valid
learn_alias_tools_present
learn_hygiene_pass
perception_artifacts_valid
perception_review
repo_signal_readiness_export
release_notes_present
```

`lint_type_quality` and `tests_pass` run only the commands you pass in
(`--lint-command` / `--test-command`); without one they warn rather than vouch
for quality that was not run. `contract_drift` blocks when the runtime exposes a
different number of `@mcp.tool()` functions than `docs/tool_contracts.json`
declares. `unsafe_commands` blocks on ungated shell/eval/exec in the server and
bridge entrypoints; string-literal pattern definitions are ignored and an
audited, gated line may be exempted with a trailing `# nosec` comment.
`perception_review` is a read-only pass that surfaces (never blocks on)
mq-image-analyze risk signals.

## CLI

```bash
mq-mcp release-gate run --repo . --target v1.4.0
mq-mcp release-gate run --repo . --target v1.4.0 --json
```

## JSON Shape

```json
{
  "repo": "mq-agent",
  "target": "v1.4.0",
  "status": "blocked",
  "score": 78,
  "blockers": [],
  "warnings": [],
  "next_actions": [],
  "checks": []
}
```
