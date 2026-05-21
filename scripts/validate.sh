#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/mq-mcp-uv-cache}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${TMPDIR:-/tmp}/mq-mcp-pycache}"

# Handles section.
section() {
  printf '\n== %s ==\n' "$1"
}

# Handles ok.
ok() {
  printf 'OK: %s\n' "$1"
}

# Handles fail.
fail() {
  printf 'FAIL: %s\n' "$1"
  exit 1
}

section "MCP tool doc check"
if [[ -x "$ROOT/scripts/check-mcp-tool-docs.sh" ]]; then
  "$ROOT/scripts/check-mcp-tool-docs.sh"
else
  fail "check-mcp-tool-docs.sh missing or not executable"
fi

section "Integration docs check"
if [[ -x "$ROOT/scripts/check-integration-docs.sh" ]]; then
  "$ROOT/scripts/check-integration-docs.sh"
else
  fail "check-integration-docs.sh missing or not executable"
fi

section "Integration smoke check"
if [[ -x "$ROOT/scripts/check-integration-smoke.sh" ]]; then
  "$ROOT/scripts/check-integration-smoke.sh"
else
  fail "check-integration-smoke.sh missing or not executable"
fi

section "Bridge tool discovery check"
if [[ -x "$ROOT/scripts/check-bridge-tool-discovery.sh" ]]; then
  "$ROOT/scripts/check-bridge-tool-discovery.sh"
else
  fail "check-bridge-tool-discovery.sh missing or not executable"
fi

section "Repo"
cd "$ROOT"
git status --short --branch
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
printf '%s\n' "$tools_output" | grep -q "list_repo_files" || fail "list_repo_files tool missing"
printf '%s\n' "$tools_output" | grep -q "search_repo" || fail "search_repo tool missing"
printf '%s\n' "$tools_output" | grep -q "git_status" || fail "git_status tool missing"
printf '%s\n' "$tools_output" | grep -q "git_diff" || fail "git_diff tool missing"
printf '%s\n' "$tools_output" | grep -q "validate_project" || fail "validate_project tool missing"
printf '%s\n' "$tools_output" | grep -q "update_repo_file" || fail "update_repo_file tool missing"

ok "Core MCP tools found"

section "Bridget identity"
if compgen -G "$ROOT/.assets/*.jpg" >/dev/null || compgen -G "$ROOT/assets/bridget*.jpg" >/dev/null; then
  ok "Bridget image assets found"
else
  fail "No Bridget images found in .assets/*.jpg or assets/bridget*.jpg"
fi

face_output="$(uv run python bridge.py "hur ser du ut?" 2>/dev/null)"
[[ -n "$face_output" ]] || fail "Bridget face output looks empty"
ok "Bridget face trigger works"

section "README bridge smoke test"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  uv run python bridge.py "Read README.md and summarize it briefly."
  ok "Bridge can read root README.md"
else
  echo "SKIP: OPENAI_API_KEY is not set, skipping OpenAI bridge prompt"
fi

section "Done"
ok "mq-mcp validation completed"
