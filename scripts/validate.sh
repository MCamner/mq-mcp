#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/mq-mcp-uv-cache}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${TMPDIR:-/tmp}/mq-mcp-pycache}"

FAILED=0

# Handles section.
section() {
  printf '\n== %s ==\n' "$1"
}

# Handles ok.
ok() {
  printf 'OK: %s\n' "$1"
}

# Handles fail — records the failure, does not exit.
fail() {
  printf 'FAIL: %s\n' "$1" >&2
  FAILED=$((FAILED + 1))
}

section "Runtime truth check"
if [[ -x "$ROOT/scripts/check-runtime-truth.sh" ]]; then
  "$ROOT/scripts/check-runtime-truth.sh" || fail "check-runtime-truth.sh failed"
else
  fail "check-runtime-truth.sh missing or not executable"
fi

section "MCP tool doc check"
if [[ -x "$ROOT/scripts/check-mcp-tool-docs.sh" ]]; then
  "$ROOT/scripts/check-mcp-tool-docs.sh" || fail "check-mcp-tool-docs.sh failed"
else
  fail "check-mcp-tool-docs.sh missing or not executable"
fi

section "Integration docs check"
if [[ -x "$ROOT/scripts/check-integration-docs.sh" ]]; then
  "$ROOT/scripts/check-integration-docs.sh" || fail "check-integration-docs.sh failed"
else
  fail "check-integration-docs.sh missing or not executable"
fi

section "Integration smoke check"
if [[ -x "$ROOT/scripts/check-integration-smoke.sh" ]]; then
  "$ROOT/scripts/check-integration-smoke.sh" || fail "check-integration-smoke.sh failed"
else
  fail "check-integration-smoke.sh missing or not executable"
fi

section "Bridge tool discovery check"
if [[ -x "$ROOT/scripts/check-bridge-tool-discovery.sh" ]]; then
  "$ROOT/scripts/check-bridge-tool-discovery.sh" \
    || fail "check-bridge-tool-discovery.sh failed"
else
  fail "check-bridge-tool-discovery.sh missing or not executable"
fi

section "Semantic memory audit"
if [[ -x "$ROOT/scripts/check-semantic-memory.sh" ]]; then
  "$ROOT/scripts/check-semantic-memory.sh" \
    || fail "check-semantic-memory.sh failed"
else
  fail "check-semantic-memory.sh missing or not executable"
fi

section "Tool contracts check"
if [[ -x "$ROOT/scripts/check-tool-contracts.sh" ]]; then
  "$ROOT/scripts/check-tool-contracts.sh" \
    || fail "check-tool-contracts.sh failed"
else
  fail "check-tool-contracts.sh missing or not executable"
fi

section "Profile templates check"
if [[ -x "$ROOT/scripts/check-profiles.py" ]]; then
  "$ROOT/scripts/check-profiles.py" \
    || fail "check-profiles.py failed"
else
  fail "check-profiles.py missing or not executable"
fi

section "Stability baseline check"
if [[ -x "$ROOT/scripts/check-stability.py" ]]; then
  "$ROOT/scripts/check-stability.py" \
    || fail "check-stability.py failed"
else
  fail "check-stability.py missing or not executable"
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
python -m compileall bridge.py server.py main.py >/dev/null \
  || fail "Python compile failed"
ok "Python files compile"

section "MCP tool listing"
tools_output="$(uv run python bridge.py --tools)" \
  || { fail "bridge.py --tools failed"; tools_output=""; }
printf '%s\n' "$tools_output"

grep -q "read_repo_file"    <<< "$tools_output" || fail "read_repo_file tool missing"
grep -q "get_system_resources" <<< "$tools_output" || fail "get_system_resources tool missing"
grep -q "list_repo_files"  <<< "$tools_output" || fail "list_repo_files tool missing"
grep -q "search_repo"      <<< "$tools_output" || fail "search_repo tool missing"
grep -q "git_status"       <<< "$tools_output" || fail "git_status tool missing"
grep -q "git_diff"         <<< "$tools_output" || fail "git_diff tool missing"
grep -q "validate_project" <<< "$tools_output" || fail "validate_project tool missing"
grep -q "update_repo_file" <<< "$tools_output" || fail "update_repo_file tool missing"

ok "Core MCP tools found"

section "Bridget identity"
if compgen -G "$ROOT/.assets/*.jpg" >/dev/null || compgen -G "$ROOT/assets/bridget*.jpg" >/dev/null; then
  ok "Bridget image assets found"
else
  echo "SKIP: Bridget image assets not found — local-only, skipping image check"
fi

uv run python bridge.py "hur ser du ut?" >/dev/null 2>&1 \
  || { fail "Bridget face trigger crashed"; }
ok "Bridget face trigger works"

section "README bridge smoke test"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  uv run python bridge.py "Read README.md and summarize it briefly."
  ok "Bridge can read root README.md"
else
  echo "SKIP: OPENAI_API_KEY is not set, skipping OpenAI bridge prompt"
fi

section "Done"
if [[ "$FAILED" -eq 0 ]]; then
  ok "mq-mcp validation completed"
else
  printf 'FAIL: %d check(s) failed — fix issues above before releasing\n' \
    "$FAILED" >&2
  exit 1
fi
