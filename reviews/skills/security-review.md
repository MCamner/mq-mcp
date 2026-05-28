# Skill: Security Pattern Recognition

This skill is injected alongside a security review contract to help the
reviewer identify language- and file-type-specific dangerous patterns.

---

## Python files (.py)

High-risk patterns to look for:

- `os.system(` — executes shell string directly; user input → shell injection
- `subprocess.*shell=True` — shell metacharacters in any argument become injection
- `eval(` / `exec(` — arbitrary code execution if argument is user-controlled
- `os.popen(` — shell execution, same risk as os.system
- `pickle.loads(` / `pickle.load(` — arbitrary code execution on untrusted data
- `yaml.load(` without `Loader=yaml.SafeLoader` — unsafe deserialization
- String formatting into shell commands: `f"cmd {user_input}"` passed to subprocess
- `open(path, 'w')` on a path not validated by resolve_repo_file or resolve_allowed_local_file
- `os.environ` passed directly to subprocess without filtering
- Hardcoded secrets: `api_key = "sk-…"`, `password = "…"`, `token = "…"`
- `__import__(user_input)` — dynamic import of user-controlled module names

Low-risk patterns (note, not flag):

- `subprocess.run([...], shell=False)` with a static list — safe
- `resolve_repo_file` / `resolve_allowed_local_file` applied before file access — safe
- `_redacted_env()` used for diagnostic output — safe

---

## Shell files (.sh, .bash, .zsh)

High-risk patterns:

- `eval "$var"` or `eval $(cmd)` — arbitrary code execution
- Unquoted variable expansion in command position: `cmd $USER_INPUT` (no quotes)
- `rm -rf $VAR` — unquoted variable in destructive command
- `curl … | bash` — remote code execution
- `source $VAR` — sourcing user-controlled path
- Credentials assigned then exported: `export PASSWORD=…`

Low-risk patterns (note):

- Quoted variables: `"$VAR"` — safe from word-splitting
- Fixed argument lists with no user input — safe

---

## JSON files (.json)

Security-relevant observations:

- Credentials, tokens, or private keys in cleartext values
- `"subprocess": true` tools without approval gate documentation
- Profile files that include Class D tools for Class A/B callers

---

## MCP tool definitions (server.py)

Extra patterns specific to MCP servers:

- Tool that returns user-controlled content verbatim (prompt injection risk)
- Tool that constructs a shell command from its arguments
- Tool that forwards os.environ to a subprocess
- Tool with `write: true` classified as Class A in tool_contracts.json
- Tool that reads from `MQ_MCP_ALLOWED_PATHS` but skips resolve_allowed_local_file
