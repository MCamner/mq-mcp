#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"

printf '== mq-mcp upgrade ==\n'
printf 'repo: %s\n\n' "$ROOT"

command -v uv >/dev/null 2>&1 || {
  printf 'ERROR: uv is required. Install it from https://docs.astral.sh/uv/\n' >&2
  exit 1
}

cd "$ROOT"
git pull --ff-only origin main
uv --directory "$APP" sync
uv tool install "$APP" --force
"$ROOT/scripts/validate.sh"

printf '\nUpgrade complete. Current version: '
uv --directory "$APP" run python main.py version
