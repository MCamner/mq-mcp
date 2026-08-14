# Bridget and mq-agent Boundary

Bridget is the local execution assistant. `mq-agent` is the workflow
orchestrator. The boundary is based on who must own the plan and its state, not
only on how many commands a request contains.

## Decision rule

Use Bridget directly for a bounded local task that can normally be completed in
one to five steps without maintaining workflow state. Use `mq-agent` when the
task needs planning, sequencing across repositories, retries, routing, a
long-running workflow, or coordination between agents.

The one-to-five-step range is operator guidance, not a policy bypass or a hard
runtime limit. A short request still belongs in `mq-agent` if it needs
orchestration; a longer conversational exchange may remain in Bridget when each
turn is an independent, bounded action.

| Bridget owns | `mq-agent` owns |
| --- | --- |
| Local, bounded execution | Workflow planning and task decomposition |
| Conversational context and bounded session summaries | Workflow state, sequencing, and retries |
| Calling declared mq-mcp tools under their safety classes | Tool routing and cross-repo coordination |
| Showing a delegation preview | Approval flow for an orchestrated run |
| Presenting an mq-agent plan or result | Agent handoffs and long-running work |

Bridget must not select tools for a workflow, persist workflow state, implement
retry policy, bypass tool approvals, or start nested workflows. Session history
is conversational context, not orchestration state or evidence.

## Examples

| Request | Owner | Reason |
| --- | --- | --- |
| Read one file and summarize it | Bridget | One bounded local action |
| Review a local diff with a declared review tool | Bridget | Bounded execution through mq-mcp |
| Inspect a symbol and its callers | Bridget | Read-only CodeGraph context lookup |
| Plan, edit, test, commit, and push | `mq-agent` | Sequenced multi-step workflow with state |
| Update `mq-mcp` and `mq-agent` together | `mq-agent` | Cross-repository coordination |
| Run a release-readiness workflow and handle failures | `mq-agent` | Planning, gates, and retries |

## Delegation flow

For an explicit workflow, use:

```bash
bridget --workflow "review and test"
```

Bridget may identify the repository, propose one of the known workflow
templates, ask `mq-agent` for a plan, display that plan, and request approval.
Only after approval does it ask `mq-agent` to run the workflow. Bridget remains
a thin entrypoint and does not own the run.

For an ordinary prompt that is clearly multi-step, cross-repository, or
explicitly complex, Bridget may print a deterministic delegation suggestion.
The suggestion is preview-only: it starts nothing and the user must invoke the
displayed `bridget --workflow` command. Interactive chat prints at most one
suggestion per session.

Nested workflows are denied with the `MQ_WORKFLOW_DEPTH` guard. The delegated
child runs `mq-agent workflow`; Bridget does not build arbitrary shell chains.

## Related contracts

- [`orchestration-boundary.md`](orchestration-boundary.md) defines ownership
  across the MQ stack.
- [`ORCHESTRATION_CONTRACT.md`](ORCHESTRATION_CONTRACT.md) defines the formal
  Bridget-to-mq-agent delegation contract.
- [`RUNTIME_CONTRACT.md`](RUNTIME_CONTRACT.md) defines what mq-mcp guarantees
  to callers.
