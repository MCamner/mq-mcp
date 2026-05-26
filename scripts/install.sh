#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"
ENV_FILE="$APP/.env"
ENV_EXAMPLE="$APP/.env.example"

printf '== mq-mcp install ==\n'
printf 'repo: %s\n\n' "$ROOT"

command -v uv >/dev/null 2>&1 || {
  printf 'ERROR: uv is required. Install it from https://docs.astral.sh/uv/\n' >&2
  exit 1
}

if [[ ! -f "$ENV_FILE" && -f "$ENV_EXAMPLE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  printf 'Created %s from .env.example\n' "$ENV_FILE"
else
  printf 'Keeping existing %s\n' "$ENV_FILE"
fi

uv --directory "$APP" sync
uv tool install "$APP" --force

printf '\nInstalled mq-mcp command:\n'
printf '  mq-mcp doctor\n'
printf '  mq-mcp tools\n'
printf '  mq-mcp serve\n'
printf '\n'
uv --directory "$APP" run python main.py doctor

if ! command -v mq-mcp >/dev/null 2>&1; then
  printf '\nNOTE: mq-mcp is installed by uv, but its bin directory is not on PATH in this shell yet.\n'
  printf 'Run `uv tool dir --bin` to find the directory to add to PATH.\n'
fi
