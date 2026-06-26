#!/usr/bin/env bash
# Release readiness gate for mq-mcp.
# Runs all governance checks and reports every failure before exit.
# Usage: ./scripts/release-check.sh [--dry-run]
#   --dry-run  Run all checks but do not require a clean git tree.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/mq-mcp-uv-cache}"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
FAILED=0
WARNED=0

RED='\033[1;31m'; GREEN='\033[1;32m'; BLUE='\033[1;34m'; YELLOW='\033[0;33m'; RESET='\033[0m'

# Handles pass.
pass()    { printf "${GREEN}[PASS]${RESET} %s\n"   "$*"; }
# Handles fail.
fail()    { printf "${RED}[FAIL]${RESET} %s\n"     "$*" >&2; FAILED=$((FAILED + 1)); }
# Handles warn.
warn()    { printf "${YELLOW}[WARN]${RESET} %s\n"  "$*"; WARNED=$((WARNED + 1)); }
# Handles skip.
skip()    { printf "${BLUE}[SKIP]${RESET} %s\n"    "$*"; }
# Handles section.
section() { printf "\n${BLUE}=== %s ===${RESET}\n" "$*"; }

VERSION="$(cat VERSION)"

printf "${BLUE}mq-mcp release-check — v%s${RESET}\n" "$VERSION"
if [[ "$DRY_RUN" == true ]]; then
  printf "${YELLOW}[dry-run mode — git tree check skipped]${RESET}\n"
fi
printf '\n'

# ---------------------------------------------------------------------------
# 1. Git working tree
# ---------------------------------------------------------------------------
section "Git state"
if [[ "$DRY_RUN" == false ]]; then
  if git diff --quiet && git diff --cached --quiet && \
     [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
    pass "Git working tree is clean"
  else
    fail "Git working tree is not clean — commit or stash changes first"
    git status --short
  fi
else
  skip "Git tree check skipped in dry-run mode"
fi

# ---------------------------------------------------------------------------
# 2. Runtime truth (version sync, tool count, safety doc coverage)
# ---------------------------------------------------------------------------
section "Runtime truth"
if [[ -x "$REPO_ROOT/scripts/check-runtime-truth.sh" ]]; then
  if "$REPO_ROOT/scripts/check-runtime-truth.sh"; then
    pass "Runtime truth check passed"
  else
    fail "Runtime truth check failed — version or tool count drift detected"
  fi
else
  fail "check-runtime-truth.sh missing or not executable"
fi

# ---------------------------------------------------------------------------
# 3. Tool contracts and safety class enforcement
# ---------------------------------------------------------------------------
section "Tool contracts"
if [[ -x "$REPO_ROOT/scripts/check-tool-contracts.sh" ]]; then
  if "$REPO_ROOT/scripts/check-tool-contracts.sh"; then
    pass "Tool contracts check passed"
  else
    fail "Tool contracts check failed — missing entries or safety class violations"
  fi
else
  fail "check-tool-contracts.sh missing or not executable"
fi

# ---------------------------------------------------------------------------
# 4. Semantic memory audit
# ---------------------------------------------------------------------------
section "Semantic memory"
if [[ -x "$REPO_ROOT/scripts/check-semantic-memory.sh" ]]; then
  if "$REPO_ROOT/scripts/check-semantic-memory.sh"; then
    pass "Semantic memory audit passed"
  else
    fail "Semantic memory audit failed — store.json structural error"
  fi
else
  fail "check-semantic-memory.sh missing or not executable"
fi

# ---------------------------------------------------------------------------
# 5. Full validate.sh (integration smoke, profiles, stability, bridge)
# ---------------------------------------------------------------------------
section "Full validation"
if [[ -x "$REPO_ROOT/scripts/validate.sh" ]]; then
  if "$REPO_ROOT/scripts/validate.sh"; then
    pass "validate.sh passed"
  else
    fail "validate.sh failed — see output above for details"
  fi
else
  fail "scripts/validate.sh missing or not executable"
fi

# ---------------------------------------------------------------------------
# 6. Python compile
# ---------------------------------------------------------------------------
section "Python compile"
if python -m compileall mq-mcp/ -q 2>/dev/null; then
  pass "Python files compile without errors"
else
  fail "Python compile failed"
fi

# ---------------------------------------------------------------------------
# 7. Tests
# ---------------------------------------------------------------------------
section "Test suite"
if uv --directory mq-mcp run pytest ../tests -q --tb=short 2>&1; then
  pass "All tests passed"
else
  fail "Test suite failed — fix failing tests before release"
fi

# ---------------------------------------------------------------------------
# 8. Version sync
# ---------------------------------------------------------------------------
section "Version sync"

PYPROJECT_VER="$(grep '^version' mq-mcp/pyproject.toml | sed 's/version = "\(.*\)"/\1/')"
if [[ "$VERSION" == "$PYPROJECT_VER" ]]; then
  pass "VERSION ($VERSION) matches pyproject.toml ($PYPROJECT_VER)"
else
  fail "VERSION mismatch: VERSION=$VERSION, pyproject.toml=$PYPROJECT_VER"
fi

if grep -qF "version-${VERSION}-" README.md; then
  pass "README badge references version $VERSION"
else
  fail "README badge does not reference version $VERSION"
fi

if grep -qF "releases/tag/v${VERSION}" README.md; then
  pass "README release link references version $VERSION"
else
  fail "README release link does not reference version $VERSION"
fi

if grep -qE "^## ${VERSION}" CHANGELOG.md; then
  pass "CHANGELOG has entry for version $VERSION"
else
  fail "CHANGELOG missing entry for version $VERSION (run: ./release.sh --init-changelog $VERSION)"
fi

STABILITY_VER="$(python3 -c "import json; print(json.load(open('docs/stability.json')).get('version',''))" 2>/dev/null || echo "")"
if [[ "$STABILITY_VER" == "$VERSION" ]]; then
  pass "docs/stability.json version matches ($VERSION)"
else
  fail "docs/stability.json version mismatch: has '$STABILITY_VER', expected '$VERSION'"
fi

CONTRACTS_VER="$(python3 -c "import json; print(json.load(open('docs/tool_contracts.json')).get('mq_mcp_version',''))" 2>/dev/null || echo "")"
if [[ "$CONTRACTS_VER" == "$VERSION" ]]; then
  pass "docs/tool_contracts.json mq_mcp_version matches ($VERSION)"
else
  fail "docs/tool_contracts.json mq_mcp_version mismatch: has '$CONTRACTS_VER', expected '$VERSION'"
fi

# ---------------------------------------------------------------------------
# 9. Generated artifacts
# ---------------------------------------------------------------------------
section "Generated artifacts"
GENERATED="$REPO_ROOT/generated"
if cd mq-mcp && uv run python main.py tools --export >/dev/null 2>&1; then
  pass "Tool registry export succeeded"
  for artifact in tool-index.json tool-safety.json runtime-contract.json tool-policies.json; do
    if python3 -c "import json; json.load(open('../generated/$artifact'))" 2>/dev/null; then
      pass "generated/$artifact is valid JSON"
    else
      fail "generated/$artifact is missing or invalid"
    fi
  done
  cd ..
else
  cd ..
  fail "mq-mcp tools --export failed — generated artifacts cannot be produced"
fi

# ---------------------------------------------------------------------------
# 10. CI status
# ---------------------------------------------------------------------------
section "CI status"
if command -v gh >/dev/null 2>&1; then
  CI_JSON="$(gh run list --repo MCamner/mq-mcp --branch main --limit 5 \
    --json name,status,conclusion 2>/dev/null || echo "[]")"
  VALIDATE_CONCLUSION="$(python3 -c "
import json, sys
runs = json.loads(sys.stdin.read())
for r in runs:
    if 'Validate' in r.get('name','') and r.get('status') == 'completed':
        print(r.get('conclusion','unknown'))
        break
else:
    print('not_found')
" <<< "$CI_JSON")"
  case "$VALIDATE_CONCLUSION" in
    success) pass "CI Validate workflow: success" ;;
    failure) fail "CI Validate workflow: failure — fix CI before tagging" ;;
    not_found) warn "CI Validate workflow: no completed run found" ;;
    *)       warn "CI Validate workflow: $VALIDATE_CONCLUSION" ;;
  esac
else
  skip "gh CLI not available — skipping CI status check"
fi

# ---------------------------------------------------------------------------
# 11. Required docs
# ---------------------------------------------------------------------------
section "Required docs"
for doc in docs/orchestration-boundary.md docs/ORCHESTRATION_CONTRACT.md \
           docs/integration.md docs/stability.json docs/TOOL_SAFETY.md \
           docs/RUNTIME_CONTRACT.md semantic_memory/POLICY.md; do
  if [[ -f "$doc" ]]; then
    pass "$doc exists"
  else
    fail "$doc missing"
  fi
done

# ---------------------------------------------------------------------------
# 12. Shell syntax
# ---------------------------------------------------------------------------
section "Shell syntax"
for script in scripts/validate.sh scripts/release-check.sh \
              scripts/install.sh scripts/upgrade.sh scripts/uninstall.sh; do
  if [[ -f "$script" ]]; then
    if bash -n "$script" 2>/dev/null; then
      pass "$script syntax OK"
    else
      fail "$script has syntax errors"
    fi
  else
    skip "$script not found"
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n'
printf '%0.s─' {1..60}
printf '\n'

if [[ "$FAILED" -eq 0 && "$WARNED" -eq 0 ]]; then
  printf "${GREEN}=== release-check PASSED — ready for v%s ===${RESET}\n" "$VERSION"
  exit 0
elif [[ "$FAILED" -eq 0 ]]; then
  printf "${YELLOW}=== release-check PASSED with %d warning(s) — review before release ===${RESET}\n" "$WARNED"
  exit 0
else
  printf "${RED}=== release-check FAILED — %d failure(s), %d warning(s) — fix before releasing ===${RESET}\n" \
    "$FAILED" "$WARNED"
  exit 1
fi
