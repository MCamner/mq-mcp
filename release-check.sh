#!/usr/bin/env bash
# Root release readiness check for mq-mcp. Read-only.
#
# Human mode (no flags / --dry-run): prints per-check ok/FAIL, exits 1 on any
#   failure.
# Contract mode (--json): emits a repo_release_check.v1 object on stdout and
#   exits 0 (the `status` field carries the verdict). Consumed by mq-agent's
#   `stack release --all --preflight`.
#
# This is the canonical, read-only entrypoint. It runs mq-mcp's own read-only
# governance checks; it does NOT run scripts/release-check.sh, which exports the
# tool registry (a write) and so is not preflight-safe. --dry-run is accepted;
# this check never mutates the tree.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
VERSION="$(cat VERSION)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

DRY_RUN=0
JSON=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --json) JSON=1 ;;
    *) echo "usage: ./release-check.sh [--dry-run] [--json]" >&2; exit 2 ;;
  esac
done
: "$DRY_RUN"

BLOCKERS=()
COMPILE_CACHE="$(mktemp -d)"
trap 'rm -rf "$COMPILE_CACHE"' EXIT
say()  { [[ "$JSON" -eq 1 ]] || echo "$1"; }
ok()   { [[ "$JSON" -eq 1 ]] || echo "  ok: $1"; }
fail() { BLOCKERS+=("$1"); [[ "$JSON" -eq 1 ]] || echo "FAIL: $1" >&2; }

run() {
  local label="$1"; shift
  local out
  if out="$("$@" 2>&1)"; then
    ok "$label"
  else
    fail "$label"
    [[ "$JSON" -eq 1 ]] || printf '%s\n' "$out" >&2
  fi
}

say "=== mq-mcp release-check v${VERSION} ==="

say "--- Version surfaces ---"
CONTRACT_VER="$("$PYTHON_BIN" -c "import json; print(json.load(open('.mq/repo-contract.json'))['version'])" 2>/dev/null)"
if [[ "$CONTRACT_VER" == "$VERSION" ]]; then
  ok ".mq/repo-contract.json matches VERSION ($VERSION)"
else
  fail ".mq/repo-contract.json version '$CONTRACT_VER' != VERSION '$VERSION'"
fi
if grep -q "$VERSION" CHANGELOG.md 2>/dev/null; then
  ok "CHANGELOG references $VERSION"
else
  fail "CHANGELOG does not reference $VERSION"
fi
if grep -q "$VERSION" README.md 2>/dev/null; then
  ok "README references $VERSION"
else
  fail "README does not reference $VERSION"
fi

say "--- Governance checks ---"
run "runtime truth (version/tool-count/safety coverage)" bash scripts/check-runtime-truth.sh
run "tool contracts (entries + safety classes)" bash scripts/check-tool-contracts.sh
run "semantic memory audit" bash scripts/check-semantic-memory.sh

say "--- Python compile ---"
run "compileall mq-mcp" env PYTHONPYCACHEPREFIX="$COMPILE_CACHE" \
  "$PYTHON_BIN" -m compileall -q -x '(^|/)\.venv/' mq-mcp/

# Note: generated/ tool artifacts are gitignored and produced by the tool
# registry export (a write). Their presence/validity is enforced by CI on push,
# not here — this entrypoint stays read-only and works on a fresh checkout.

if [[ "$JSON" -eq 1 ]]; then
  status=READY
  [[ "${#BLOCKERS[@]}" -gt 0 ]] && status=BLOCKED
  "$PYTHON_BIN" - "$status" "$VERSION" ${BLOCKERS[@]+"${BLOCKERS[@]}"} <<'PY'
import json
import sys

status, version, *blockers = sys.argv[1:]
print(json.dumps({
    "schema": "repo_release_check.v1",
    "repo": "mq-mcp",
    "status": status,
    "blockers": blockers,
    "warnings": [],
    "evidence": {"version": version},
}))
PY
  exit 0
fi

say ""
if [[ "${#BLOCKERS[@]}" -eq 0 ]]; then
  echo "=== All checks passed — v${VERSION} governance is green ==="
else
  echo "=== ${#BLOCKERS[@]} check(s) failed — fix before releasing ===" >&2
  exit 1
fi
