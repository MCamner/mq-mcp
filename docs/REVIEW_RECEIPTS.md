# Review Receipts

mq-mcp can return a content-bound receipt for a review without changing the
normal review result contract.

Set `receipt=true` on:

- `review_file`
- `review_diff`
- `review_repo`
- `risk_review_file`
- `risk_review_diff`

The returned schema is `mq.review-receipt.v1`.

## What a receipt proves

A receipt binds the review result to:

- the subject repository;
- the exact git commit observed by mq-mcp;
- the exact source bytes in review scope;
- the mq-mcp runtime identity that performed the review; and
- a SHA-256 digest of the returned review result.

A commit alone is not sufficient because a review may run against a dirty
working tree. The receipt therefore records a content fingerprint of the actual
review scope.

## Scope

For a file review, the receipt hashes that file.

For a diff review, it hashes the reviewable changed files selected from
`git diff --name-only HEAD` using the same supported extensions as the review
surface: `.py`, `.sh`, `.md`, and `.json`.

For a repo review, it hashes the Python source tree while excluding hidden
directories, `.git`, `.venv`, `node_modules`, and `__pycache__`.

## Stability gate

mq-mcp snapshots the subject before the review and again afterwards.

- `ISSUED` means the exact subject fingerprint was stable for the whole review.
- `REFUSED` with `subject-changed-during-review` means the source changed
  while the review was running.
- `REFUSED` with `subject-commit-unavailable` means mq-mcp could hash the
  source but could not bind it to a git commit.

A refused receipt still carries the raw review result and its digest; it does
not claim that result is safely bound to one immutable code version.

## Safety

Receipt generation is read-only. It does not write a receipt file, modify the
reviewed repository, stage changes, fetch refs, or contact GitHub. Existing
review-memory behavior is unchanged.

The caller decides whether and where a returned receipt should be persisted.
