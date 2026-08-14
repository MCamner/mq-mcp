# Bridget memory boundary

Bridget uses bounded local context to continue recent conversations. This is temporary working memory, not durable knowledge, runtime evidence, or an autonomous learning source.

## Declared local persistence

Normal session recording writes only these three redacted surfaces under `~/.mq`:

| Path | Purpose | Retention |
|---|---|---|
| `bridget-context.md` | Rolling compatibility view | Last five recorded sessions |
| `bridget-history.jsonl` | History and bounded prompt source | Append-only until date deletion |
| `bridget_memory/sessions/YYYY-MM-DD.jsonl` | Date-partitioned deletion surface | Append-only until date deletion |

`bridget-project` is a separate explicit project pin written only by `bridget --project <repo>`. It contains the selected repository name and path, not conversation text.

Phase 6 adds one separate, declared aggregate metrics surface:

| Path | Purpose | Content boundary |
|---|---|---|
| `bridget-metrics.jsonl` | Daily Bridget outcome counters | Date, fixed metric name, positive integer only |

The metrics file may count completed commands and sessions, explicit workflow
delegations, learn suggestions and accepted storage, and history/project-context
hits. It never contains prompts, answers, repositories, paths, tool names,
arguments, or session identifiers. Metrics are local and best-effort: a write
failure cannot fail the Bridget command. Use `bridget --metrics [1-365]` to
inspect daily counts and totals. The JSONL store is append-only until the user
removes it; the dashboard reads at most the requested 365-day window. Set
`BRIDGET_METRICS_DISABLED=1` to disable collection. Repository validation sets
this automatically so smoke tests are not recorded as real usage.

Live `--chat` messages exist only in process memory. Bridget records one redacted session summary when the chat exits; it does not persist every turn. Prompt injection uses at most three recorded sessions, at most 500 characters each, and nothing older than seven days.

There is no automatic session upload, cloud sync, mqobsidian write, semantic-memory write, or learn-store write. Explicit Class C tools such as `record_learning` or `brain_record_session` remain separate operations with their own approval requirements.

## Evidence and promotion

Session text is context only:

- it never counts as validation evidence
- it never auto-promotes to `learn_engine/memory/lessons.jsonl` or mqobsidian
- it may only trigger a preview suggestion after an evidence-producing tool ran
- storing that candidate requires a separate `--learn-last` preview and explicit approval

Code, tests, review findings, or other declared evidence sources must independently support a learning record.

## Commands

```bash
bridget --history [N]            # inspect recent temporary summaries
bridget --continue               # show the latest summary and pinned repo state
bridget --project [repo]         # inspect or set the separate project pin
bridget --forget YYYY-MM-DD      # preview, approve, then delete one date
bridget --learn-last [file]      # separate redacted learn preview and approval
bridget --metrics [N]            # local content-free daily counters
```

`--forget` removes the selected date from all three session surfaces. It does not touch learning, reviews, semantic memory, mqobsidian, the project pin, or aggregate metrics.

## Verification

`tests/test_bridget_context.py` asserts the exact files created by normal session recording, redaction across all stores, bounded injection, and date-scoped deletion. `tests/test_bridget_metrics.py` asserts the fixed content-free metrics schema, aggregation, malformed-row handling, and dashboard bounds. `tests/test_bridge_refactor.py` asserts that context-only tools do not produce a learn suggestion and that learning writes suppress further suggestions.

The architectural ownership rule is recorded in [`ADR-007`](../architecture_memory/decisions/ADR-007-context-ownership-boundaries.md).
