#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "OK: $*"; }

require_file() {
  [[ -f "$1" ]] || fail "Missing required file: $1"
  ok "Found $1"
}

require_text() {
  grep -Fq "$2" "$1" || fail "Missing '$2' in $1"
  ok "$1 mentions: $2"
}

echo "INTEGRATION DOCS CHECK"
echo "======================"

require_file "docs/integration.md"
require_file "docs/integration.html"
require_file "docs/TOOL_SAFETY.md"
require_file "README.md"

require_text "docs/integration.md" "mq-mcp + mq-hal + repo-signal"
require_text "docs/integration.md" "hal_repo_report"
require_text "docs/integration.md" "repo_signal_analyze"
require_text "docs/integration.md" "repo_signal_checklist"
require_text "docs/integration.md" "tool_safety_report"
require_text "docs/integration.md" "MQ_MCP_LOCAL_REPOS"
require_text "docs/integration.md" "read-only"

require_text "docs/integration.html" "mq-mcp + mq-hal + repo-signal"
require_text "docs/integration.html" "hal_repo_report"
require_text "docs/integration.html" "repo_signal_analyze"
require_text "docs/integration.html" "repo_signal_checklist"

require_text "README.md" "integration.md"

echo ""
echo "OK: integration docs check passed"
