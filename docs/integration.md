# mq-mcp Integration Map

This document explains how `mq-mcp` fits into the MQ ecosystem alongside
`mq-agent`, `mq-hal`, `repo-signal`, and `mq-image-analyze`.

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
