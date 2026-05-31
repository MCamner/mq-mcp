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

# ---------------------------------------------------------------------------
# Safety class contract enforcement
# ---------------------------------------------------------------------------
printf '\nSAFETY CLASS ENFORCEMENT\n'

python3 - <<'PY'
import json, sys

d = json.load(open("docs/tool_contracts.json"))
failed = 0

def fail(msg):
    global failed
    print(f"FAIL: {msg}", file=sys.stderr)
    failed += 1

def ok(msg):
    print(f"OK: {msg}")

class_counts = {"A": 0, "B": 0, "C": 0, "D": 0}

for t in d["tools"]:
    name = t["name"]
    cls  = t.get("class", "")
    w    = bool(t.get("write", False))
    sub  = bool(t.get("subprocess", False))
    desc = t.get("description", "")
    fx   = t.get("side_effects", [])
    res  = t.get("resolver", "none")

    # Every tool must have required fields
    if not cls:
        fail(f"{name}: missing 'class' field")
        continue
    if cls not in ("A", "B", "C", "D"):
        fail(f"{name}: unknown class '{cls}'")
        continue
    if not desc:
        fail(f"{name}: missing description")
    if not name:
        fail(f"{name}: missing name")

    class_counts[cls] = class_counts.get(cls, 0) + 1

    # Class A: no file writes, no arbitrary subprocess (git reads allowed)
    if cls == "A":
        if w:
            fail(f"Class A violation — write=true: {name}")
        if sub and res != "run_repo_command":
            fail(f"Class A violation — subprocess=true outside git boundary: {name}")

    # Class B: no file writes
    elif cls == "B":
        if w:
            fail(f"Class B violation — write=true: {name}")

    # Class C: must write, must document side effects
    elif cls == "C":
        if not w:
            fail(f"Class C violation — write=false: {name}")
        if not fx:
            fail(f"Class C violation — side_effects empty: {name}")

    # Class D: must use subprocess, must document side effects
    elif cls == "D":
        if not sub:
            fail(f"Class D violation — subprocess=false: {name}")
        if not fx:
            fail(f"Class D violation — side_effects empty: {name}")

for cls, count in sorted(class_counts.items()):
    ok(f"Class {cls}: {count} tools")

if failed == 0:
    print("OK: all safety class contracts satisfied")
    sys.exit(0)
else:
    print(f"FAIL: {failed} safety class violation(s)", file=sys.stderr)
    sys.exit(1)
PY

ENFORCE_EXIT=$?
if [[ "$ENFORCE_EXIT" -ne 0 ]]; then
  FAILED=$((FAILED + 1))
fi

printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  printf 'OK: tool contracts check passed\n'
else
  printf 'FAIL: %d issue(s) found in tool contracts\n' "$FAILED" >&2
  exit 1
fi
