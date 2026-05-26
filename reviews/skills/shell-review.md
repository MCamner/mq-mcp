# Review Skill: Shell — Comment Review

## When to use

Apply this skill when reviewing `.sh` files under the `comment` mode.

---

## Shell-specific guidance

### Header and purpose

- Scripts longer than 20 lines should have a comment block at the top explaining:
  - what the script does
  - what arguments it accepts (if any)
  - what it modifies (if anything)

### Function documentation

- Functions should have a one-line comment above them explaining their purpose
- Flag functions with no description that have non-obvious behavior

### Safety annotations

- Commands that delete, overwrite, or mutate files should have a comment explaining intent
- `rm -rf`, `git reset --hard`, `sudo`, and `chmod` calls should be annotated
- Unquoted variables (`$VAR` vs `"$VAR"`) that could cause word splitting should be flagged

### Exit codes and error handling

- Scripts that do not `set -e` or `set -euo pipefail` should be noted
- Commands whose failure is silently ignored (`;` chaining, `|| true`) without comment should be noted

### Inline comments

- Flag comments that repeat the command in English ("# list files" above `ls`)
- Highlight comments that explain WHY a non-obvious flag is used

---

## Severity defaults

| Finding                              | Default severity |
| ------------------------------------ | ---------------- |
| Missing script header on long script | MISSING          |
| Unquoted variable near rm/mv/cp      | WARNING          |
| Silent error suppression             | NOTE             |
| Missing set -e or equivalent         | NOTE             |
| Repeated-command comment             | SUGGESTION       |
