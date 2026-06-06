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
version_consistent
changelog_updated
readme_current
roadmap_current
contracts_valid
safety_classes_valid
learn_hygiene_pass
perception_artifacts_valid
repo_signal_readiness_export
release_notes_present
```

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
