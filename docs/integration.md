# mq-mcp Integration Map

This document explains how `mq-mcp` fits into the MQ ecosystem alongside
`mq-agent`, `mq-hal`, `repo-signal`, `mq-image-analyze`, and `mq-ums`.

For the full orchestration boundary — which repo owns what and which tools
require explicit approval — see [`docs/orchestration-boundary.md`](orchestration-boundary.md).

---

## Ecosystem roles

| Repo               | Role                                                              |
|--------------------|-------------------------------------------------------------------|
| `mq-mcp`           | Local tool surface, safety enforcement, review engine, memory     |
| `mq-agent`         | Planning, routing, and multi-step orchestration                   |
| `mq-hal`           | System status, repo reports, and operator summaries               |
| `repo-signal`      | Repo health scoring, publish readiness, and quality metrics       |
| `mq-image-analyze` | Visual perception, screenshots, and image reasoning               |
| `mq-ums`           | Enterprise endpoint operator surface for IGEL UMS workflows       |
| `mqlaunch`         | macOS menu and terminal launcher for local workflows              |

---

## mq-mcp + mq-hal + repo-signal integration

The most common local stack is:

```text
mq-mcp + mq-hal + repo-signal
= local AI assistant + safe repo analysis + publish-quality checks
```

### Integration tools

| MCP tool                 | Delegates to  | Purpose                                          | Safety |
|--------------------------|---------------|--------------------------------------------------|--------|
| `hal_repo_report`        | mq-hal CLI    | Read-only repo report (audit, brief, ci, status) | D      |
| `repo_signal_analyze`    | repo-signal   | Repo analysis on a local path                    | B      |
| `repo_signal_checklist`  | repo-signal   | Publish readiness checklist                      | B      |
| `repo_signal_inspect`    | repo-signal   | Structured inspect.v1 data                       | B      |
| `repo_signal_doctor_json`| repo-signal   | Structured doctor.v1 data                        | B      |
| `repo_signal_status`     | (local)       | Export pack presence and merge status            | A      |
| `tool_safety_report`     | (local)       | MCP tool safety classifications                  | A      |
| `list_local_repos`       | (local)       | Registered repos from MQ_MCP_LOCAL_REPOS         | A      |

---

## mq-mcp + mq-agent integration

`mq-agent` calls `mq-mcp` as its execution runtime. The division is:

```text
mq-agent decides what to do.
mq-mcp does it.
```

mq-mcp exposes `tool_safety_report` and `validate_orchestration_contract`
so mq-agent can inspect the available tool surface before invoking anything.

The `mq-agent` profile (`profiles/mq-agent.json`) limits auto-invocation to
Class A/B tools. Class C/D tools require explicit user approval from within
the calling orchestration layer.

### Phase 12 memory-system boundary

Phase 12, the Evidence-Based Memory System, is a cross-repo capability rather
than a local `mq-mcp` feature.

| Repo | Phase 12 responsibility |
|------|-------------------------|
| `mqobsidian` | Capability owner: schemas, storage, scoring, promotion, permanent memory |
| `mq-agent` | Primary runtime: observation writing, memory queries, workflow integration |
| `repo-signal` | Repo-state producer: freshness, repeated issue, and repeated workflow signals |
| `mq-mcp` | Review intelligence: review signals, feedback, pattern extraction, anti-pattern detection |
| `mqlaunch` | Human surface: dashboard, review queue, manual promotion, memory search |

`mq-mcp` may emit validated `memory-observation.v1` and `feedback-signal.v1`
records once the upstream schemas exist. It must not own the promotion pipeline,
durable Obsidian curation, repo-health scoring, or workflow orchestration.

Local Phase 12D draft contracts live in:

* `schemas/memory-observation.v1.schema.json`
* `schemas/feedback-signal.v1.schema.json`

The runtime helper for producing validated, redacted payloads is
`mq-mcp/phase12_signals.py`.

Read-only MCP tools expose the same payload builders to orchestration and
launcher surfaces:

* `phase12_review_observation`
* `phase12_repeated_bug_observation`
* `phase12_anti_pattern_observation`
* `phase12_architecture_feedback`

---

## mq-mcp + mq-ums integration

`mq-ums` is already partially visible to the MQ stack, but today it is still
more of an adjacent enterprise tool than a first-class control-plane provider.

Current read-only integration:

| MCP tool              | Reads from                       | Purpose                              | Safety |
|-----------------------|----------------------------------|--------------------------------------|--------|
| `ums_command_catalog` | `MQ_UMS_DIR/config/commands.json`| Show the allowlisted mq-ums commands | B      |
| `ums_audit_log`       | `MQ_UMS_DIR/logs`                | Read local mq-ums audit history      | B      |

What this gives today:

* visibility into the mq-ums command surface
* read-only access to local mq-ums audit trails
* a safe path to inspect how the UMS tool is configured

What is still missing:

* a stable live-readiness contract such as `ums_status.v1`
* a single read-only health signal that `mq-agent` can consume in stack checks
* truth export of UMS readiness into longer-lived MQ memory surfaces
* a clear operator-facing endpoint status view alongside repo/runtime status

Target direction:

```text
mq-ums live validation
  -> ums_status.v1
  -> mq-mcp read-only wrapper
  -> mq-agent stack endpoint-check
  -> mqobsidian truth export
  -> mq-agent dashboard / mq-hal brief
```

Boundary rule:

`mq-mcp` should only expose bounded, read-only wrappers around mq-ums facts.
PowerShell execution logic, browser UI, and UMS mutation behavior stay owned by
`mq-ums` itself.

---

## Local repo registration

Register known repos with `MQ_MCP_LOCAL_REPOS` so integration tools can
reference them by name:

```bash
export MQ_MCP_LOCAL_REPOS="/Users/mansys/repo-signal,/Users/mansys/mq-hal,/Users/mansys/macos-scripts"
```

Do not use this for arbitrary system paths.

---

## Example prompts

**Ask for repo status via mq-hal:**

```bash
bridget "run hal repo report for mq-mcp"
```

**Ask for repo-signal analysis:**

```bash
bridget "run repo signal analyze for mq-mcp"
```

**Ask for publish checklist:**

```bash
bridget "run repo signal checklist for mq-mcp"
```

**Check tool safety map:**

```bash
bridget "show tool safety report"
```

**Start from mqlaunch:**

```bash
mqlaunch agent mcp-status
mqlaunch agent mcp-tools
```

Target invocation flow:

```text
mqlaunch
  → mq-agent (plans and routes)
  → mq-mcp (executes declared tools)
  → mq-hal / repo-signal (external reads)
```

---

## Safety rules

1. Default to Class A/B (read-only) tools.
2. Keep repo access scoped through registered local repositories.
3. Do not auto-invoke Class C/D tools — they require explicit user approval.
4. Do not commit secrets, tokens, private machine paths, or `.env` files.
5. Keep write-capable tools documented in `docs/TOOL_SAFETY.md`.
6. Validate documentation whenever a new MCP tool is added.

---

## Integration smoke test

```bash
./scripts/check-integration-smoke.sh
./scripts/check-bridge-tool-discovery.sh
```

The smoke test verifies that the main integration tools are present in
`server.py`, `README.md`, `docs/integration.md`, `docs/TOOL_SAFETY.md`,
and `scripts/validate.sh`.
