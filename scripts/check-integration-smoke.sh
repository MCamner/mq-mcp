#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Handles fail.
fail() { echo "FAIL: $*" >&2; exit 1; }
# Handles ok.
ok()   { echo "OK: $*"; }

# Handles require file.
require_file() {
  [[ -f "$1" ]] || fail "Missing required file: $1"
  ok "Found $1"
}

# Handles require text.
require_text() {
  grep -Fq "$2" "$1" || fail "Missing '$2' in $1"
  ok "$1 mentions: $2"
}

# Handles require tool everywhere.
require_tool_everywhere() {
  local tool="$1"
  require_text "mq-mcp/server.py"   "$tool"
  require_text "README.md"           "$tool"
  require_text "docs/integration.md" "$tool"
  require_text "docs/TOOL_SAFETY.md" "$tool"
}

echo "INTEGRATION SMOKE CHECK"
echo "======================="
echo ""

require_file "mq-mcp/server.py"
require_file "README.md"
require_file "docs/integration.md"
require_file "docs/TOOL_SAFETY.md"
require_file "scripts/validate.sh"

echo ""
echo "Checking core integration tools..."
echo ""

require_tool_everywhere "hal_repo_report"
require_tool_everywhere "repo_signal_analyze"
require_tool_everywhere "repo_signal_checklist"
require_tool_everywhere "tool_safety_report"
require_tool_everywhere "list_local_repos"

echo ""
echo "Checking integration concepts..."
echo ""

require_text "docs/integration.md" "mq-mcp + mq-hal + repo-signal"
require_text "docs/integration.md" "MQ_MCP_LOCAL_REPOS"
require_text "docs/integration.md" "mqlaunch"
require_text "README.md"           "Integration map"
require_text "README.md"           "repo-quality stack"

echo ""
echo "Checking validation wiring..."
echo ""

require_text "scripts/validate.sh" "check-integration-docs.sh"
require_text "scripts/validate.sh" "check-integration-smoke.sh"

echo ""
echo "OK: integration smoke check passed"
