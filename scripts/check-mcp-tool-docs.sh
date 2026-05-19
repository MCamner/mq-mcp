#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SERVER="mq-mcp/server.py"
DOC="docs/TOOL_SAFETY.md"
README="README.md"

required_doc_terms=(
  "resolve_repo_file"
  "resolve_allowed_local_file"
  "MQ_MCP_ALLOWED_PATHS"
  "write"
  "subprocess"
)

required_server_terms=(
  "resolve_repo_file"
  "resolve_allowed_local_file"
  "allowed_external_roots"
)

echo "MCP TOOL DOC CHECK"
echo "=================="

for file in "$SERVER" "$DOC" "$README"; do
  [[ -f "$file" ]] || { echo "FAIL: missing $file"; exit 1; }
done

tools_output="$(python3 - <<'PY'
import ast
from pathlib import Path

tree = ast.parse(Path("mq-mcp/server.py").read_text(encoding="utf-8"))

def is_mcp_tool(node):
    if isinstance(node, ast.Call):
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "tool"
        and isinstance(node.value, ast.Name)
        and node.value.id == "mcp"
    )

for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if any(is_mcp_tool(d) for d in node.decorator_list):
            print(node.name)
PY
)"

if [[ -z "$tools_output" ]]; then
  echo "FAIL: no @mcp.tool() functions detected in $SERVER"
  exit 1
fi

tool_count="$(printf '%s\n' "$tools_output" | wc -l | tr -d ' ')"
echo "Detected $tool_count MCP tools:"
printf '%s\n' "$tools_output" | while IFS= read -r t; do printf ' - %s\n' "$t"; done
echo

while IFS= read -r tool; do
  grep -Fq "$tool" "$DOC"    || { echo "FAIL: $tool missing from $DOC"; exit 1; }
  grep -Fq "$tool" "$README" || { echo "FAIL: $tool missing from $README"; exit 1; }
done <<< "$tools_output"

for term in "${required_doc_terms[@]}"; do
  grep -Fqi "$term" "$DOC" || { echo "FAIL: required term missing from $DOC: $term"; exit 1; }
done

for term in "${required_server_terms[@]}"; do
  grep -Fq "$term" "$SERVER" || { echo "FAIL: required implementation term missing from $SERVER: $term"; exit 1; }
done

echo "OK: every @mcp.tool() in server.py is documented in $DOC and $README"
echo "OK: safety scope terms present"
echo "OK: resolver implementation terms present"
