#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SERVER="mq-mcp/server.py"
DOC="docs/TOOL_SAFETY.md"
README="README.md"

required_terms=(
  "resolve_repo_file"
  "resolve_allowed_local_file"
  "MQ_MCP_ALLOWED_PATHS"
  "write"
  "subprocess"
)

echo "MCP TOOL DOC CHECK"
echo "=================="

for file in "$SERVER" "$DOC" "$README"; do
  [[ -f "$file" ]] || { echo "FAIL: missing $file"; exit 1; }
done

mapfile -t tools < <(
  python3 - <<'PY'
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
)

if [[ "${#tools[@]}" -eq 0 ]]; then
  echo "FAIL: no @mcp.tool() functions detected in $SERVER"
  exit 1
fi

echo "Detected ${#tools[@]} MCP tools:"
printf ' - %s\n' "${tools[@]}"
echo

for tool in "${tools[@]}"; do
  grep -q "$tool" "$DOC"    || { echo "FAIL: $tool missing from $DOC"; exit 1; }
  grep -q "$tool" "$README" || { echo "FAIL: $tool missing from $README"; exit 1; }
done

for term in "${required_terms[@]}"; do
  grep -qi "$term" "$DOC" || { echo "FAIL: required term missing from $DOC: $term"; exit 1; }
done

echo "OK: every @mcp.tool() in server.py is documented in $DOC and $README"
echo "OK: safety scope terms present"
