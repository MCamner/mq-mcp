# Review Contract: Security Review

## Purpose

This contract governs security reviews produced by the mq-mcp review engine.

A security review inspects subprocess safety, filesystem boundary enforcement,
environment variable handling, injection risks, and unsafe API exposure.
It does not modify code. It does not review comment quality or architecture.

---

## Hard Rules

### What the model MUST do

- Output only structured findings using the severity format defined below
- Cite the file path and line number for every finding
- Use the exact severity labels defined in this contract
- Be specific: name the variable, call site, or pattern that is the risk
- Distinguish between actual vulnerabilities and theoretical concerns
- Express uncertainty explicitly: "unclear whether X is validated upstream"

### What the model MUST NOT do

- Modify code under any circumstances
- Produce architecture or comment-quality findings
- Generate executable patches or diffs
- Flag secure patterns as risks without justification
- Assert exploitability without evidence in the file

---

## Severity Labels

Every finding must start with exactly one of these labels:

```text
NOTE    — informational observation, no action required
WARNING — potential risk that should be reviewed before shipping
RISK    — active security or safety issue in current code
```

No other labels are permitted in security reviews.

---

## Output Format

Each finding must follow this exact structure:

```text
[SEVERITY] file_path:line_number
<one sentence describing the security finding>
```

Example:

```text
[RISK] mq-mcp/server.py:1502
review_file constructs a prompt by embedding raw file content with no size
limit — a crafted file could exhaust context window budget or inject
instructions into the system prompt via the file body.

[WARNING] mq-mcp/server.py:905
show_notification passes user-supplied title and message directly into an
osascript string with only quote-escaping — other special characters in
osascript syntax are not sanitized.

[WARNING] mq-mcp/bridge.py:395
run_bridge passes os.environ.copy() to StdioServerParameters — all parent
process environment variables, including secrets not in MQ_MCP_*, are
forwarded to the server subprocess.

[NOTE] mq-mcp/server.py:216
resolve_repo_file uses Path.resolve() before relative_to() check, which
correctly prevents symlink-based traversal.
```

---

## Scope

A security review covers:

- **Subprocess injection:** shell=True, unvalidated arguments, command construction
  from user input
- **Path traversal:** missing or bypassed resolve_repo_file / resolve_allowed_local_file
- **Prompt injection:** user-controlled content embedded in LLM system prompts
- **Secret leakage:** API keys, tokens, or credentials printed, logged, or returned
- **Environment forwarding:** sensitive env vars passed to subprocesses
- **Input validation:** missing size limits, type checks, or allowlists at trust
  boundaries
- **osascript injection:** unescaped content passed to AppleScript strings

A security review does NOT cover:

- Comment or docstring quality (use comment-review)
- Architecture boundaries (use architecture-review)
- Performance or scalability
- Test coverage

---

## Uncertainty

If the reviewer cannot confirm a risk without tracing to another file:

```text
[WARNING] mq-mcp/server.py:450
open_in_app passes the resolved path to subprocess open — unclear whether
the MIME type or file extension is validated before the OS opens it.
```

Do not assert exploitability if the validation may happen in a caller.

---

## Limits

- Maximum 15 findings per file
- Do not flag risks that are already explicitly blocked by existing guards
  (e.g., do not flag path traversal if resolve_repo_file is correctly applied)
- If a file has no findings: output `OK — no security review findings.`

---

## Contract Version

```text
version: 1.0
scope: security-review
model-behavior: findings-only, no-code-changes
severity-labels: NOTE, WARNING, RISK
max-findings: 15
```
