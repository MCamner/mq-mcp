# Explicit workflow targets

`git_status`, `git_diff`, `review_diff` and `run_tests` accept `repo_path` as
an absolute Git repository root with an existing HEAD. The existing external
path allowlist applies; invalid or disallowed targets return `status: ERROR`
without falling back to the server repository. Worktrees are supported.

Explicit targets return structured results containing `repo_path` and
`git_commit`. Git and pytest results include the actual process exit code;
pytest output is bounded and reports truncation. `git_diff` includes staged
and unstaged changes against HEAD. Untracked files are outside this scope.
`run_tests` uses the server's `python3 -m pytest` runtime, with a 120 second
limit; it does not select the target repository's virtual environment.

`review_diff` forwards the target to each file review. It reports changed,
eligible and completed file counts separately, including unsupported/deleted
files and the existing ten-file cap. Completion is not a correctness verdict:
`verification` remains `unknown`. Optional `context` is limited to 12000
characters and added to the existing review prompt as untrusted repository
data. Review API and review-memory side effects remain those of `review_file`.
`receipt=true` wraps the structured review result in the existing review receipt.

Calls without `repo_path` retain their existing behavior. `repo_signal_status`
also accepts `repo_path` to inspect that target's existing export packs, retaining
its text response. Launcher health tools describe the launcher environment.
