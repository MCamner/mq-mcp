---
id: ADR-004
title: Review contracts drive all review output format and scope
date: 2026-05-28
status: accepted
area: review, contracts, review_engine
---

## Decision

Every AI review pass must be driven by an explicit review contract loaded from
`reviews/contracts/`. The contract defines severity labels, output format, scope
boundaries, max findings, and uncertainty handling. No review prompt may ask
the model to "review this file" without a loaded contract in the system prompt.

## Rationale

Without a contract, review output format varies per call, severity labels are
inconsistent, and the model may exceed scope (rewriting code, adding features,
commenting on style). Contracts make review output machine-parseable by
`severity_engine.py` and comparable across runs.

## Consequences

- `review_file(mode=X)` loads `reviews/contracts/{X}-review.md` before the model call.
- Adding a new review mode requires a new contract file, not just a prompt change.
- Golden reviews in `reviews/golden/` serve as calibration references for each
  contract and skill combination.
- The `MultiPassReviewer` injects the contract in Pass 2 and the consistency
  checker uses the same output format in Pass 3.
