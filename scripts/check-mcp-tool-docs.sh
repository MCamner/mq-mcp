#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SAFETY_DOC="docs/TOOL_SAFETY.md"
README="README.md"

tools=(
  get_system_resources
  read_repo_file
  list_repo_files
  search_repo
  git_status
  git_diff
  validate_project
  update_repo_file
  run_mqlaunch
  analyze_csv
  analyze_guitar_pro
  open_in_app
  edit_image
)

required_safety_terms=(
  "resolve_repo_file"
  "resolve_allowed_local_file"
  "MQ_MCP_ALLOWED_PATHS"
  "write"
  "subprocess"
)

echo "MCP TOOL DOC CHECK"
echo "=================="

[[ -f "$SAFETY_DOC" ]] || { echo "FAIL: missing $SAFETY_DOC"; exit 1; }
[[ -f "$README" ]]     || { echo "FAIL: missing $README"; exit 1; }

for tool in "${tools[@]}"; do
  grep -q "$tool" "$SAFETY_DOC" || { echo "FAIL: $tool missing from $SAFETY_DOC"; exit 1; }
  grep -q "$tool" "$README"     || { echo "FAIL: $tool missing from $README"; exit 1; }
done

for term in "${required_safety_terms[@]}"; do
  grep -qi "$term" "$SAFETY_DOC" || { echo "FAIL: required term missing from $SAFETY_DOC: $term"; exit 1; }
done

echo "OK: all 13 MCP tools documented in $SAFETY_DOC and $README"
echo "OK: safety scope terms present"
