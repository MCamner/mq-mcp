---
name: terminal-ui-polisher
description: Use when improving mq-mcp terminal output, Bridget CLI usage, validation scripts, release scripts, mqlaunch command surface, help screens, or status/error messages.
---

# Terminal UI Polisher

Use this skill to make mq-mcp's terminal surfaces clearer, calmer, and easier to debug.

## Terminal Surfaces

- `mq-mcp/bridge.py` usage, `--tools`, `--search`, and error output
- `mq-mcp/mqlaunch.sh`
- `scripts/validate.sh`
- `scripts/release-check.sh`
- `scripts/check-*.sh`
- `release.sh`
- README command examples
- docs under `docs/demo.md`, `docs/install.md`, and `docs/troubleshooting.md`

## Principles

- Keep status output compact and scan-friendly.
- Make failures actionable with exact file, command, or missing tool.
- Preserve scriptability for checks that CI or humans parse.
- Keep `bridge.py --tools` readable and usable without network credentials.
- Avoid decorative output that hides validation failures.
- Do not change exit codes casually.

## Checklist

Review:

- command usage text
- working-directory assumptions
- success/failure markers
- skipped checks and why they were skipped
- timeout/error messages
- long lines in terminal output
- color use in scripts
- copy-paste safety of commands
- consistency between README examples and actual CLI behavior

## Verification

```bash
bash -n scripts/validate.sh scripts/release-check.sh release.sh
./scripts/validate.sh
uv --directory mq-mcp run python bridge.py --help
uv --directory mq-mcp run python bridge.py --tools
```

For script-only copy changes, `bash -n` plus the focused script may be enough.

## Output Standard

When reviewing terminal UX, lead with confusing or risky output first, then propose exact text or code changes. When editing, keep the style consistent with the existing `section`, `ok`, `fail`, `pass`, and `step` helpers.
