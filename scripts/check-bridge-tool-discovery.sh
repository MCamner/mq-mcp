#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/mq-mcp"

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/mq-mcp-uv-cache}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${TMPDIR:-/tmp}/mq-mcp-pycache}"

# Handles fail.
fail() { echo "FAIL: $*" >&2; exit 1; }
# Handles ok.
ok() { echo "OK: $*"; }

# Handles require text.
require_text() {
  local text="$1"
  local pattern="$2"
  printf '%s\n' "$text" | grep -Fq -- "$pattern" || fail "Bridge tool catalog missing: $pattern"
  ok "Bridge tool catalog includes $pattern"
}

echo "BRIDGE TOOL DISCOVERY CHECK"
echo "==========================="

test -f "$APP_DIR/bridge.py" || fail "Missing mq-mcp/bridge.py"
test -f "$APP_DIR/server.py" || fail "Missing mq-mcp/server.py"

cd "$APP_DIR"

tools_output="$(uv run python bridge.py --tools)"

require_text "$tools_output" "Available MCP tools:"
require_text "$tools_output" "read_repo_file"
require_text "$tools_output" "list_repo_files"
require_text "$tools_output" "search_repo"
require_text "$tools_output" "git_status"
require_text "$tools_output" "git_diff"
require_text "$tools_output" "validate_project"
require_text "$tools_output" "tool_safety_report"
require_text "$tools_output" "list_local_repos"
require_text "$tools_output" "repo_signal_analyze"
require_text "$tools_output" "repo_signal_checklist"
require_text "$tools_output" "hal_repo_report"

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  prompt_output="$(uv run python bridge.py "List the available MCP tools." 2>/dev/null || true)"
  [[ -n "$prompt_output" ]] || fail "Bridge prompt returned empty output"
  ok "Bridge prompt smoke returned output"
else
  echo "SKIP: OPENAI_API_KEY is not set, skipping live prompt smoke"
fi

echo
echo "OK: bridge tool discovery check passed"
