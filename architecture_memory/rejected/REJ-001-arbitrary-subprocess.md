---
id: REJ-001
title: Rejected — arbitrary subprocess execution from tool arguments
date: 2026-05-28
status: rejected
area: safety, server
---

## Rejected pattern

Allowing MCP tools to execute arbitrary shell commands constructed from
tool arguments (e.g., `subprocess.run(shlex.split(user_input))`).

## Why rejected

Arbitrary subprocess execution is command injection waiting to happen.
A tool that executes `subprocess.run(cmd)` where `cmd` comes from the model
or from a caller-supplied argument has no safety boundary. Any prompt injection
that reaches the tool call layer can execute arbitrary code on the host machine.

Additionally, arbitrary subprocess tools cannot be classified under the
A-D safety model — they are inherently Class D with an unbounded blast radius.

## What we do instead

Class D tools invoke a single, fixed, declared subprocess command.
The command is hardcoded in the tool definition; arguments may be constrained
but the executable is never caller-supplied. Example: `open_vscode` always
calls `open -a "Visual Studio Code"`, never `open -a {user_app}`.
