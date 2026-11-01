#!/usr/bin/env bash
# Model-backed Bridget smoke checks: README prompt and REPL start/exit.
#
# Exit codes: 0 = both ran and passed, 1 = a check failed, 2 = skipped because
# no OpenAI key is available (neither OPENAI_API_KEY nor the Keychain item).
#
# The key is never read here. Keychain is only asked whether the item exists
# (no -w); scripts/bridget reads it into its own process environment. Every run
# uses a temporary MQ_BRIDGET_CONTEXT_DIR, so the operator's ~/.mq history is
# neither read nor written.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGET_BIN="${MQ_BRIDGET_BIN:-$ROOT_DIR/scripts/bridget}"
SECURITY_BIN="${MQ_SECURITY_BIN:-/usr/bin/security}"
KEYCHAIN_SERVICE="${MQ_OPENAI_KEYCHAIN_SERVICE:-mq-openai-api-key}"
KEYCHAIN_ACCOUNT="${MQ_OPENAI_KEYCHAIN_ACCOUNT:-${USER:-$(id -un)}}"

FAILED=0

# Handles fail — records the failure, does not exit.
fail() { echo "FAIL: $*" >&2; FAILED=$((FAILED + 1)); }
# Handles ok.
ok()   { echo "OK: $*"; }

# Whether a key is available, without reading the secret.
key_available() {
  [[ -n "${OPENAI_API_KEY:-}" ]] && return 0
  [[ -x "$SECURITY_BIN" ]] || return 1
  "$SECURITY_BIN" find-generic-password \
    -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" >/dev/null 2>&1
}

if ! key_available; then
  echo "SKIP: no OpenAI key (OPENAI_API_KEY or Keychain '$KEYCHAIN_SERVICE') — README and REPL smoke not run"
  exit 2
fi

ctx_dir="$(mktemp -d)"
trap 'rm -rf "$ctx_dir"' EXIT
export MQ_BRIDGET_CONTEXT_DIR="$ctx_dir"
export MQ_MCP_HOME="$ROOT_DIR"

if readme_out="$("$BRIDGET_BIN" "Read README.md and summarize it briefly." </dev/null 2>&1)" \
    && [[ -n "$readme_out" ]]; then
  printf '%s\n' "$readme_out"
  ok "Bridge can read root README.md"
else
  printf '%s\n' "$readme_out" >&2
  fail "Bridget README prompt failed"
fi

# An immediate 'exit' exercises REPL setup and the clean exit path without
# spending an OpenAI completion. Must greet and exit 0.
if repl_out="$("$BRIDGET_BIN" --chat <<< 'exit' 2>&1)" \
    && grep -q "Hej då" <<< "$repl_out"; then
  ok "Bridget --chat REPL starts and exits cleanly"
else
  printf '%s\n' "$repl_out" >&2
  fail "Bridget --chat REPL did not exit cleanly"
fi

[[ "$FAILED" -eq 0 ]] || exit 1
