# Review Skill: MCP Tool — Comment Review

## When to use

Apply this skill when reviewing MCP tool definitions in `server.py` or any
file that uses the `@mcp.tool()` decorator pattern.

---

## MCP tool-specific guidance

### Docstring requirements

Every `@mcp.tool()` function must have a docstring that describes:

1. What the tool does (first sentence)
2. What it returns
3. Args: block with each parameter described

Flag tools that are missing any of these three elements.

### Safety class documentation

Tools that touch the filesystem, run subprocesses, or open external apps
should document their safety boundary in the docstring. Example:

```text
Read-only. Repo-scoped. No subprocess.
```

Flag tools that have subprocess or filesystem side effects with no safety note.

### Path parameter documentation

Tools that accept a `path` or `relative_path` parameter should document:

- whether the path is repo-relative or absolute
- what happens if the path is outside the allowed boundary

### Error return format

Tools should return human-readable error strings (not raise exceptions)
because the MCP protocol surfaces tool output directly to the model.
Flag tools that may raise unhandled exceptions on bad input.

### Tool naming

- Tool names should be `snake_case`
- Tools that are read-only should not have names that imply mutation (`get_`, `list_`, `show_`, `read_` are safe prefixes)
- Tools that mutate should have explicit mutation names (`update_`, `set_`, `create_`)

---

## Severity defaults

| Finding                                    | Default severity |
| ------------------------------------------ | ---------------- |
| Missing docstring                          | MISSING          |
| Missing Args: block                        | MISSING          |
| Subprocess tool with no safety note        | WARNING          |
| Path tool with no boundary documentation  | WARNING          |
| Misleading tool name (mutation vs read)    | WARNING          |
| Missing return format description          | SUGGESTION       |
