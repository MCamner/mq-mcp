# Review Skill: Python — Comment Review

## When to use

Apply this skill when reviewing `.py` files under the `comment` mode.

---

## Python-specific guidance

### Docstrings

- Public functions, classes, and methods should have docstrings
- Docstrings must describe WHAT the function returns, not just WHAT it does
- One-liner docstrings are acceptable for trivial functions
- Do not flag private functions (prefixed `_`) for missing docstrings

### Type hints

- Public function signatures should have return type annotations
- Parameters that accept multiple types should use `X | Y` (Python 3.10+) not `Union[X, Y]`
- Flag `Any` used in public APIs without justification
- Do not flag `Any` in test files

### Inline comments

- Flag comments that say WHAT the code does (readable code is self-documenting)
- Highlight comments that say WHY — these are valuable and should not be removed
- Flag TODO/FIXME/HACK comments without a ticket reference or date

### Naming

- Flag parameter names that are single letters (except loop indices `i`, `j`, `k`)
- Flag overly abbreviated variable names: `res`, `ret`, `tmp`, `d`, `l`
- Flag inconsistent naming conventions within the same module (snake_case vs camelCase)

### Module level

- Flag module-level code with side effects (not wrapped in `if __name__ == "__main__"`)
- Flag missing module docstring on files larger than 100 lines

---

## Severity defaults

| Finding                          | Default severity |
| -------------------------------- | ---------------- |
| Missing docstring on public func | MISSING          |
| Missing return type hint         | SUGGESTION       |
| Misleading comment               | WARNING          |
| Unclear parameter name           | SUGGESTION       |
| Module-level side effect         | WARNING          |
| TODO without reference           | NOTE             |
