# Review Contract: Safety Contract Review

## Purpose

This contract governs safety contract reviews produced by the mq-mcp review engine.

A safety contract review detects violations of the declared safety class model.
It checks that every tool's metadata matches its actual behavior, that Class C/D
tools have the required documentation, and that no tool silently crosses its
declared boundary.

It is especially useful when reviewing server.py diffs to catch new tools added
without complete metadata.

---

## Hard Rules

### What the model MUST do

- For every new `@mcp.tool` function found in the file, check whether it has
  a corresponding entry in `docs/tool_contracts.json`
- Flag any Class A tool that calls `subprocess.run`, `os.system`, or `open()`
  with a write mode outside the `resolve_repo_file` / `run_repo_command` boundary
- Flag any Class C tool that does not return the modified file path
- Flag any Class D tool that calls subprocess without a documented side effect
- Flag any tool missing its safety class in docs/tool_contracts.json
- Use exact severity labels defined in this contract
- Cite the decorator line and function name for every finding

### What the model MUST NOT do

- Modify any file
- Flag tools that correctly declare their class and side effects
- Produce code quality or style findings
- Assert a violation without showing the code evidence

---

## Severity Labels

```text
CRITICAL — undeclared write, subprocess, or network call in a Class A/B tool
RISK     — Class C/D tool missing required metadata (no side_effects, no description)
WARNING  — new tool with no entry in docs/tool_contracts.json
NOTE     — informational: tool found, safety class confirmed correct
```

No other labels are permitted in safety contract reviews.

---

## Output Format

```
[SEVERITY] file_path:line_number
<one sentence identifying the tool and the specific contract violation>
```

Example:

```
[CRITICAL] mq-mcp/server.py:842
Class A tool `analyze_csv` calls open(path, 'w') — write operation violates Class A contract.

[WARNING] mq-mcp/server.py:1205
New @mcp.tool `export_report` has no entry in docs/tool_contracts.json.

[RISK] mq-mcp/server.py:1340
Class D tool `run_build` has subprocess=True but side_effects is empty in tool_contracts.json.

[NOTE] mq-mcp/server.py:316
Class A tool `read_repo_file` — resolver and contract metadata confirmed correct.
```

---

## Scope

A safety contract review covers:

- New `@mcp.tool` decorators and whether they have contract metadata
- Class A/B tools calling subprocess, open-for-write, or network calls
- Class C tools that do not document their write scope or return the modified path
- Class D tools without subprocess=true or empty side_effects
- Tools with `class=unknown` or missing class in contracts
- Auto-commit: any tool calling `subprocess.run(["git", "commit", ...])` or
  `subprocess.run(["git", "push", ...])`

A safety contract review does NOT cover:

- Code correctness beyond safety boundaries
- Naming or comment quality
- Architecture or module structure

---

## Special case: new tools in a diff

When reviewing a diff or a changed file, prioritize any `@mcp.tool` decorator
that was added or modified. For each new tool:

1. Note the class assigned in the docstring or contracts
2. Check whether a contract entry exists for it
3. Check whether write/subprocess behavior matches the declared class
4. Emit WARNING if contracts entry is missing, CRITICAL if behavior contradicts class

---

## Invariants to enforce

```
Every @mcp.tool must have an entry in docs/tool_contracts.json
Class A: write=false, subprocess=false (exception: resolver=run_repo_command)
Class B: write=false
Class C: write=true, side_effects non-empty
Class D: subprocess=true, side_effects non-empty
No tool may call git commit or git push from within the tool function
```

---

## Limits

- Maximum 15 findings per file
- If no violations found: output `OK — no safety contract violations detected.`

---

## Contract Version

```
version: 1.0
scope: safety-contract-review
model-behavior: safety-enforcement-only, no-code-changes
severity-labels: CRITICAL, RISK, WARNING, NOTE
max-findings: 15
```
