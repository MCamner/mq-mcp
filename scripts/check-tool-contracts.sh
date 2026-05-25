#!/usr/bin/env bash
# Validate that docs/tool_contracts.json covers every @mcp.tool in server.py.
# Fails if a tool is missing from the contract file or if the file is absent.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/docs/tool_contracts.json"
SERVER="$ROOT/mq-mcp/server.py"

printf 'TOOL CONTRACTS CHECK\n'
printf '====================\n'

FAILED=0

fail() { printf 'FAIL: %s\n' "$1" >&2; FAILED=$((FAILED + 1)); }
ok()   { printf 'OK: %s\n' "$1"; }

if [[ ! -f "$CONTRACT" ]]; then
  fail "docs/tool_contracts.json missing — run: python scripts/generate_tool_contracts.py"
  exit 1
fi
ok "Found docs/tool_contracts.json"

# Extract tool names from server.py (@mcp.tool decorated functions).
server_tools="$(grep -A1 '@mcp\.tool' "$SERVER" | grep 'def ' | sed 's/.*def \([a-z_]*\).*/\1/' | sort)"

# Extract tool names from contract JSON.
contract_tools="$(python3 -c "
import json, sys
d = json.load(open('$CONTRACT'))
for t in sorted(d['tools'], key=lambda x: x['name']):
    print(t['name'])
")"

tool_count="$(echo "$server_tools" | wc -l | tr -d ' ')"
contract_count="$(echo "$contract_tools" | wc -l | tr -d ' ')"

ok "server.py exposes $tool_count tools"
ok "tool_contracts.json covers $contract_count tools"

# Tools in server.py but missing from contracts.
missing="$(comm -23 <(echo "$server_tools") <(echo "$contract_tools"))"
if [[ -n "$missing" ]]; then
  fail "tools in server.py missing from tool_contracts.json:"
  printf '%s\n' "$missing" | sed 's/^/  - /'
fi

# Tools in contracts but removed from server.py.
extra="$(comm -13 <(echo "$server_tools") <(echo "$contract_tools"))"
if [[ -n "$extra" ]]; then
  fail "tools in tool_contracts.json not found in server.py (stale):"
  printf '%s\n' "$extra" | sed 's/^/  - /'
fi

# Verify schema_version field.
schema="$(python3 -c "import json; print(json.load(open('$CONTRACT'))['schema_version'])")"
if [[ "$schema" != "tool-contracts.v1" ]]; then
  fail "unexpected schema_version: $schema"
else
  ok "schema_version: $schema"
fi

printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  printf 'OK: tool contracts check passed\n'
else
  printf 'FAIL: %d issue(s) found in tool contracts\n' "$FAILED" >&2
  exit 1
fi
