#!/usr/bin/env bash
# Verify that all public version signals agree with each other and with runtime.
# Emits MQ_MCP_RUNTIME_TRUTH_ERROR lines for every mismatch found.
# Exit 0 = all checks pass. Exit 1 = at least one failure.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERVER="mq-mcp/server.py"
README="README.md"
CHANGELOG="CHANGELOG.md"
TOOL_SAFETY="docs/TOOL_SAFETY.md"
CONTRACTS="docs/tool_contracts.json"
STABILITY="docs/stability.json"
VERSION_FILE="VERSION"

FAILED=0

printf 'RUNTIME TRUTH CHECK\n'
printf '===================\n'

# Handles fail.
fail() { printf 'MQ_MCP_RUNTIME_TRUTH_ERROR: %s\n' "$1" >&2; FAILED=$((FAILED + 1)); }
# Handles ok.
ok()   { printf 'OK: %s\n' "$1"; }

# ---------------------------------------------------------------------------
# 1. VERSION file
# ---------------------------------------------------------------------------
if [[ ! -f "$VERSION_FILE" ]]; then
  fail "VERSION file missing"
else
  version="$(tr -d '[:space:]' < "$VERSION_FILE")"
  if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    ok "VERSION is semver-compatible: $version"
  else
    fail "VERSION is not semver-compatible: '$version' (expected X.Y.Z)"
    version=""
  fi
fi

if [[ -z "${version:-}" ]]; then
  printf 'Skipping version-dependent checks (VERSION invalid)\n'
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. README badge and release link
# ---------------------------------------------------------------------------
if grep -qF "version-${version}-" "$README"; then
  ok "README badge matches VERSION ($version)"
else
  fail "VERSION mismatch between VERSION ($version) and README badge"
fi

if grep -qF "releases/tag/v${version}" "$README"; then
  ok "README release link matches VERSION ($version)"
else
  fail "VERSION mismatch between VERSION ($version) and README release link"
fi

# ---------------------------------------------------------------------------
# 3. CHANGELOG
# ---------------------------------------------------------------------------
if grep -qE "^## ${version}" "$CHANGELOG"; then
  ok "CHANGELOG has entry for $version"
else
  fail "VERSION mismatch: CHANGELOG missing entry for $version"
fi

# ---------------------------------------------------------------------------
# 4. docs/stability.json
# ---------------------------------------------------------------------------
if [[ -f "$STABILITY" ]]; then
  stability_ver="$(python3 -c "import json; print(json.load(open('$STABILITY')).get('version',''))" 2>/dev/null || true)"
  if [[ "$stability_ver" == "$version" ]]; then
    ok "docs/stability.json version matches ($version)"
  else
    fail "VERSION mismatch: docs/stability.json has '$stability_ver', expected '$version'"
  fi
else
  fail "docs/stability.json missing"
fi

# ---------------------------------------------------------------------------
# 5. Runtime tool discovery — collect from server.py via AST
# ---------------------------------------------------------------------------
runtime_tools="$(python3 - <<'PY'
import ast, sys
from pathlib import Path

src = Path("mq-mcp/server.py").read_text(encoding="utf-8")
tree = ast.parse(src)

def is_mcp_tool(node):
    if isinstance(node, ast.Call):
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "tool"
        and isinstance(node.value, ast.Name)
        and node.value.id == "mcp"
    )

names = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if any(is_mcp_tool(d) for d in node.decorator_list):
            names.append(node.name)
for n in sorted(names):
    print(n)
PY
)"

if [[ -z "$runtime_tools" ]]; then
  fail "could not discover tools from $SERVER"
  exit 1
fi

runtime_count="$(printf '%s\n' "$runtime_tools" | wc -l | tr -d ' ')"
ok "Runtime tool discovery: $runtime_count tools found"

# ---------------------------------------------------------------------------
# 6. README tool count
# ---------------------------------------------------------------------------
readme_count="$(python3 -c "
import re, sys
txt = open('$README').read()
m = re.search(r'\b(\d+)\s+(?:documented[^\n]*)?tools', txt)
print(m.group(1) if m else '')
" 2>/dev/null || true)"
if [[ -z "$readme_count" ]]; then
  fail "tool count mismatch: could not find tool count in README"
elif [[ "$readme_count" == "$runtime_count" ]]; then
  ok "README tool count matches runtime ($runtime_count)"
else
  fail "tool count mismatch between README ($readme_count) and runtime ($runtime_count)"
fi

# ---------------------------------------------------------------------------
# 7. TOOL_SAFETY.md coverage — every runtime tool must appear
# ---------------------------------------------------------------------------
missing_in_safety=0
while IFS= read -r tool; do
  if ! grep -qF "$tool" "$TOOL_SAFETY"; then
    fail "tool missing from $TOOL_SAFETY: $tool"
    missing_in_safety=$((missing_in_safety + 1))
  fi
done <<< "$runtime_tools"
if [[ "$missing_in_safety" -eq 0 ]]; then
  ok "all runtime tools present in $TOOL_SAFETY"
fi

# ---------------------------------------------------------------------------
# 8. TOOL_SAFETY.md ↔ runtime — no phantom tools in docs
# ---------------------------------------------------------------------------
safety_tools="$(python3 -c "
import re
txt = open('$TOOL_SAFETY').read()
# Table rows start with | \`tool_name\`
names = re.findall(r'^\|\s+\`([a-z][a-z_]+)\`', txt, re.MULTILINE)
for n in sorted(set(names)):
    print(n)
" 2>/dev/null || true)"
phantom=0
while IFS= read -r tool; do
  [[ -z "$tool" ]] && continue
  # Use a here-string, not `printf ... | grep -q`: grep -q short-circuits on the
  # first match and closes the pipe, which SIGPIPEs printf mid-write. Under
  # `set -o pipefail` that makes the pipeline return 141 even on a match,
  # falsely flagging early-sorted tools (e.g. get_public_ip) as phantom. Flaky
  # by timing. A here-string has no upstream writer to kill.
  if ! grep -qxF "$tool" <<< "$runtime_tools"; then
    fail "tool in $TOOL_SAFETY not found in runtime: $tool"
    phantom=$((phantom + 1))
  fi
done <<< "$safety_tools"
if [[ "$phantom" -eq 0 ]]; then
  ok "no phantom tools in $TOOL_SAFETY"
fi

# ---------------------------------------------------------------------------
# 9. Class C/D tools have metadata in tool_contracts.json
# ---------------------------------------------------------------------------
if [[ -f "$CONTRACTS" ]]; then
  cd_missing="$(python3 - <<'PY'
import json
from pathlib import Path

d = json.load(open("docs/tool_contracts.json"))
missing = []
for t in d["tools"]:
    cls = t.get("safety_class") or t.get("class", "")
    if cls in ("C", "D"):
        gaps = []
        if not t.get("name"):           gaps.append("name")
        if not t.get("description"):    gaps.append("description")
        if cls not in t.get("safety_class", t.get("class", "")):
            gaps.append("safety_class")
        if "write" not in t and "writes_files" not in t:
            gaps.append("write/writes_files")
        if gaps:
            missing.append(f"{t.get('name','?')}: missing {', '.join(gaps)}")
for m in missing:
    print(m)
PY
)"
  if [[ -z "$cd_missing" ]]; then
    ok "all Class C/D tools have required metadata"
  else
    while IFS= read -r line; do
      fail "Class C/D metadata gap: $line"
    done <<< "$cd_missing"
  fi
else
  fail "$CONTRACTS missing — run: python scripts/generate_tool_contracts.py"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  ok "runtime truth check passed"
  exit 0
else
  printf 'MQ_MCP_RUNTIME_TRUTH_ERROR: %d check(s) failed\n' "$FAILED" >&2
  exit 1
fi
