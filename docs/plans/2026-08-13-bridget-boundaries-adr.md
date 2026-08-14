# Bridget Boundaries ADR Implementation Plan

## Goal

Record and validate the ownership boundaries between Bridget, mq-agent,
mqobsidian, CodeGraph, mq-mcp, and mqlaunch.

## Owner repo

mq-mcp

## Secondary repos

None modified. mqobsidian and mqlaunch are read-only evidence sources.

## Architecture boundary

- mqobsidian owns durable knowledge, context contracts, schemas, templates,
  and reviewed truth surfaces.
- mq-agent owns planning, workflow routing, task decomposition, and delegation.
- mq-mcp owns deterministic execution tools, safety metadata, and runtime
  boundaries; Bridget is its bounded interactive client.
- CodeGraph owns repo-local structural source intelligence and its database.
- mqlaunch is a thin human/operator entrypoint and status consumer.

## Non-goals

- No runtime behavior changes.
- No mqobsidian memory writes or promotion.
- No CodeGraph timeline implementation.
- No repair of tools identified as follow-up work.

## Approval gates

- Before file writes: approved by the user's request.
- Before commit: yes; separate user request required.
- Before push/merge: yes; separate user request required.
- Before deletion/settings changes: yes.

## Test gates

- `git diff --check`
- `./scripts/validate.sh`

## Rollback

Revert the ADR, roadmap checkbox, and this plan in one normal Git revert.

### Task 1: Record the boundary decision

**Purpose:** Make the four roadmap boundaries explicit and auditable.

**Files:**

- Create: `architecture_memory/decisions/ADR-007-context-ownership-boundaries.md`
- Modify: `ROADMAP.md`
- Read-only reference: mqobsidian ADR-009 and truth-surface contract

**Steps:**

1. Write the accepted decision with ownership, prohibited behavior, and
   consequences.
2. Mark the Bridget Phase 0 ADR acceptance criterion complete.
3. Run the validation gates.
4. Summarize follow-up tool drift separately.

**Expected result:**

The ADR is discoverable through architecture memory and the roadmap no longer
lists the boundary decision as missing.

**Commit suggestion:**

`docs(architecture): record context ownership boundaries`
