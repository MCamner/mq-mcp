#!/usr/bin/env bash
# Release readiness check for mq-mcp.
# Run from the repository root before every release.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

pass() { printf "\033[1;32m[PASS]\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m[FAIL]\033[0m %s\n" "$*" >&2; FAILED=1; }
step() { printf "\033[1;34m[----]\033[0m %s\n" "$*"; }

FAILED=0

VERSION="$(cat VERSION)"

step "Shell syntax: validate.sh"
bash -n scripts/validate.sh && pass "scripts/validate.sh syntax OK" || fail "scripts/validate.sh has syntax errors"

step "Python compile"
python -m compileall mq-mcp/ -q && pass "Python files compile OK" || fail "Python compile failed"

step "Run validate.sh"
./scripts/validate.sh && pass "validate.sh passed" || fail "validate.sh failed"

step "Run tests"
uv --directory mq-mcp run pytest ../tests -v && pass "tests passed" || fail "tests failed"

step "VERSION matches pyproject.toml"
PYPROJECT_VER="$(grep '^version' mq-mcp/pyproject.toml | sed 's/version = "\(.*\)"/\1/')"
if [[ "$VERSION" == "$PYPROJECT_VER" ]]; then
  pass "VERSION ($VERSION) matches pyproject.toml ($PYPROJECT_VER)"
else
  fail "VERSION mismatch: VERSION=$VERSION, pyproject.toml=$PYPROJECT_VER"
fi

step "README contains version $VERSION"
if grep -q "$VERSION" README.md; then
  pass "README references version $VERSION"
else
  fail "README does not reference version $VERSION"
fi

step "CHANGELOG contains version $VERSION"
if grep -q "$VERSION" CHANGELOG.md; then
  pass "CHANGELOG references version $VERSION"
else
  fail "CHANGELOG does not reference version $VERSION"
fi

step "No stale tool counts (13 tools, 14 tools)"
STALE=$(grep -rn '\b13 tools\b\|\b14 tools\b' README.md docs/ TOOL_INDEX.md SAFETY_MODEL.md 2>/dev/null || true)
if [[ -z "$STALE" ]]; then
  pass "No stale tool count references found"
else
  fail "Stale tool count found:"
  printf '%s\n' "$STALE"
fi

step "docs/install.md does not reference Python 3.14"
if grep -q '3\.14' docs/install.md 2>/dev/null; then
  fail "docs/install.md still references Python 3.14"
else
  pass "docs/install.md Python version OK"
fi

printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  printf "\033[1;32m=== release-check passed — ready for v%s ===\033[0m\n" "$VERSION"
else
  printf "\033[1;31m=== release-check FAILED — fix issues before releasing ===\033[0m\n"
  exit 1
fi
