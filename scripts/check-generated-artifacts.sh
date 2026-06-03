#!/usr/bin/env bash
# Verify that all generated artifacts can be reproduced and are valid JSON.
# Does NOT require the files to be committed — they are gitignored by design.
# Exit 0 = all checks pass. Exit 1 = at least one failure.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAILED=0

printf 'GENERATED ARTIFACTS CHECK\n'
printf '=========================\n'

# Handles fail.
fail() { printf 'FAIL: %s\n' "$1" >&2; FAILED=$((FAILED + 1)); }
# Handles ok.
ok()   { printf 'OK: %s\n' "$1"; }

# ---------------------------------------------------------------------------
# Reproduce all artifacts via registry export
# ---------------------------------------------------------------------------
if uv --directory "$ROOT/mq-mcp" run python main.py tools --export >/dev/null 2>&1; then
  ok "mq-mcp tools --export ran without error"
else
  fail "mq-mcp tools --export failed — registry cannot produce artifacts"
  exit 1
fi

# ---------------------------------------------------------------------------
# Validate each artifact
# ---------------------------------------------------------------------------
EXPECTED_SCHEMAS=(
  "generated/tool-index.json:tool-index.v1"
  "generated/tool-safety.json:tool-safety.v1"
  "generated/runtime-contract.json:runtime-contract.v1"
  "generated/release-state.json:release-state.v1"
  "generated/profile-index.json:profile-index.v1"
)

for entry in "${EXPECTED_SCHEMAS[@]}"; do
  artifact="${entry%%:*}"
  schema="${entry##*:}"

  if [[ ! -f "$artifact" ]]; then
    fail "$artifact missing after export"
    continue
  fi

  # Valid JSON?
  if ! python3 -c "import json; json.load(open('$artifact'))" 2>/dev/null; then
    fail "$artifact is not valid JSON"
    continue
  fi

  # Correct schema field?
  actual_schema="$(python3 -c "import json; print(json.load(open('$artifact')).get('schema',''))" 2>/dev/null)"
  if [[ "$actual_schema" == "$schema" ]]; then
    ok "$artifact — schema=$schema"
  else
    fail "$artifact — expected schema=$schema, got '$actual_schema'"
  fi
done

# ---------------------------------------------------------------------------
# Cross-check: tool-index count == runtime-contract count
# ---------------------------------------------------------------------------
index_count="$(python3 -c "import json; print(json.load(open('generated/tool-index.json'))['tool_count'])" 2>/dev/null)"
rc_count="$(python3 -c "import json; print(json.load(open('generated/runtime-contract.json'))['tool_count'])" 2>/dev/null)"

if [[ "$index_count" == "$rc_count" ]]; then
  ok "tool count consistent across artifacts: $index_count tools"
else
  fail "tool count mismatch: tool-index=$index_count, runtime-contract=$rc_count"
fi

# ---------------------------------------------------------------------------
# Cross-check: release-state version == VERSION
# ---------------------------------------------------------------------------
version="$(tr -d '[:space:]' < VERSION)"
rs_version="$(python3 -c "import json; print(json.load(open('generated/release-state.json'))['mq_mcp_version'])" 2>/dev/null)"

if [[ "$rs_version" == "$version" ]]; then
  ok "release-state version matches VERSION ($version)"
else
  fail "release-state version mismatch: has '$rs_version', expected '$version'"
fi

# ---------------------------------------------------------------------------
# Cross-check: profile-index count matches profiles/ directory
# ---------------------------------------------------------------------------
profile_dir_count="$(find profiles -name '*.json' | wc -l | tr -d ' ')"
pi_count="$(python3 -c "import json; print(json.load(open('generated/profile-index.json'))['profile_count'])" 2>/dev/null)"

if [[ "$pi_count" == "$profile_dir_count" ]]; then
  ok "profile count consistent: $pi_count profiles"
else
  fail "profile count mismatch: profile-index=$pi_count, profiles/=$profile_dir_count"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  ok "generated artifacts check passed"
  exit 0
else
  printf 'FAIL: %d check(s) failed\n' "$FAILED" >&2
  exit 1
fi
