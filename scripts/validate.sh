#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"

section() {
  printf '\n== %s ==\n' "$1"
}

ok() {
  printf 'OK: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1"
  exit 1
}

section "Repo"
cd "$ROOT"
git status --short
ok "Git status checked"

section "Required files"
for file in README.md ROADMAP.md CHANGELOG.md VERSION LICENSE mq-mcp/server.py mq-mcp/bridge.py mq-mcp/pyproject.toml; do
  [[ -f "$ROOT/$file" ]] || fail "Missing $file"
  ok "$file exists"
done

section "No debug or backup files"
bad_files="$(find "$ROOT" \( -name '*.bak' -o -name 'debug_tools.py' \) -print)"
if [[ -n "$bad_files" ]]; then
  printf '%s\n' "$bad_files"
  fail "Debug/backup files found"
fi
ok "No debug/backup files found"

section "Python compile"
cd "$APP"
python -m compileall bridge.py server.py main.py >/dev/null
ok "Python files compile"

section "MCP tool listing"
tools_output="$(uv run python bridge.py --tools)"
printf '%s\n' "$tools_output"

printf '%s\n' "$tools_output" | grep -q "read_repo_file" || fail "read_repo_file tool missing"
printf '%s\n' "$tools_output" | grep -q "get_system_resources" || fail "get_system_resources tool missing"
ok "Core MCP tools found"

section "README bridge smoke test"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  uv run python bridge.py "Read README.md and summarize it briefly."
  ok "Bridge can read root README.md"
else
  echo "SKIP: OPENAI_API_KEY is not set, skipping OpenAI bridge prompt"
fi

section "Done"
ok "mq-mcp validation completed"
