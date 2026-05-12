#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"

echo "== Repo =="
cd "$ROOT"
git status --short --branch

echo
echo "== Required files =="
for file in README.md ROADMAP.md CHANGELOG.md VERSION LICENSE mq-mcp/server.py mq-mcp/bridge.py mq-mcp/pyproject.toml; do
  test -f "$file" || { echo "FAIL: missing $file"; exit 1; }
  echo "OK: $file"
done

echo
echo "== No debug or backup files =="
bad_files="$(find "$ROOT" \( -name '*.bak' -o -name 'debug_tools.py' \) -print)"
if [ -n "$bad_files" ]; then
  echo "$bad_files"
  echo "FAIL: debug/backup files found"
  exit 1
fi
echo "OK: no debug/backup files"

echo
echo "== Python compile =="
cd "$APP"
python -m compileall bridge.py server.py main.py >/dev/null
echo "OK: Python files compile"

echo
echo "== MCP tools =="
uv run python bridge.py --tools | tee /tmp/mq-mcp-tools.txt
grep -q "read_repo_file" /tmp/mq-mcp-tools.txt
grep -q "list_repo_files" /tmp/mq-mcp-tools.txt
grep -q "search_repo" /tmp/mq-mcp-tools.txt
grep -q "git_status" /tmp/mq-mcp-tools.txt
echo "OK: core MCP tools found"

echo
echo "== Done =="
echo "OK: mq-mcp validation completed"
