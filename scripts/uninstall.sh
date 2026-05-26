#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/mq-mcp/.env"
REMOVE_ENV=0

if [[ "${1:-}" == "--remove-env" ]]; then
  REMOVE_ENV=1
fi

printf '== mq-mcp uninstall ==\n'

if command -v uv >/dev/null 2>&1; then
  uv tool uninstall mq-mcp || true
else
  printf 'SKIP: uv not found, cannot remove uv tool install\n'
fi

if [[ "$REMOVE_ENV" -eq 1 ]]; then
  rm -i "$ENV_FILE"
else
  printf 'Keeping local config: %s\n' "$ENV_FILE"
  printf 'Run scripts/uninstall.sh --remove-env to remove it interactively.\n'
fi
