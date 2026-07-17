#!/usr/bin/env bash

set -euo pipefail

DRY_RUN=false
GITHUB_RELEASE=false
INIT_CHANGELOG=false
VERSION=""

VERSION_FILE="VERSION"
README_FILE="README.md"
CHANGELOG_FILE="CHANGELOG.md"
# Every version surface release-check.sh validates against VERSION. release.sh
# used to bump only VERSION and the README badge, leaving these five behind — so
# v2.0.1 was tagged with all of them still at 2.0.0. The pre-flight gate runs
# before the bump and cannot catch drift the bump itself creates.
PYPROJECT_FILE="mq-mcp/pyproject.toml"
STABILITY_FILE="docs/stability.json"
TOOL_CONTRACTS_FILE="docs/tool_contracts.json"
CONTRACT_FILE=".mq/repo-contract.json"
GEN_TOOL_CONTRACTS="scripts/generate_tool_contracts.py"


# Shows usage.
show_usage() {
  cat <<'USAGE'
Usage:
  ./release.sh [--dry-run] [--github-release] [--init-changelog] <version>

Examples:
  ./release.sh 0.1.2
  ./release.sh --dry-run 0.1.2
  ./release.sh --github-release 0.1.2
  ./release.sh --init-changelog 0.1.2

What it does:
  1. Verifies git working tree is clean
  2. Verifies required files exist
  3. Syncs with origin/main for live releases
  4. Verifies tag v<version> does not already exist
  5. Updates VERSION
  6. Updates README version badge and release link when present
  7. Bumps pyproject.toml, docs/stability.json and .mq/repo-contract.json,
     and regenerates docs/tool_contracts.json — every version surface
     release-check.sh validates against VERSION
  8. Verifies CHANGELOG.md contains the version
  9. Re-gates: verifies every version surface now matches VERSION (post-bump)
 10. Shows a diff preview
 11. Creates a release commit
 12. Creates annotated tag v<version>
 13. Pushes main and the new tag to origin
 14. Regenerates and pushes wiki Command-Reference (warn-only)
 15. Optionally creates a GitHub Release via gh CLI

Special mode:
  --init-changelog
    Creates a changelog template for the requested version at the top of
    CHANGELOG.md, then exits without commit/tag/push.

Safety:
  - --dry-run performs local checks and file updates, shows the diff,
    then rolls changes back and exits without fetch/commit/tag/push.
  - If the script aborts before commit, every bumped version surface is
    restored.
USAGE
}

# Handles log step.
log_step() {
  printf '==> %s\n' "$1"
}

# Handles error.
error() {
  printf 'ERROR: %s\n' "$1" >&2
}

# Handles rollback local changes.
rollback_local_changes() {
  git checkout -- \
    "${VERSION_FILE}" "${README_FILE}" \
    "${PYPROJECT_FILE}" "${STABILITY_FILE}" "${TOOL_CONTRACTS_FILE}" "${CONTRACT_FILE}" \
    2>/dev/null || true
  log_step "Rolled back local file changes"
}

# Handles on error.
on_error() {
  error "Release command failed with exit code: $?"
  rollback_local_changes || true
}

trap on_error ERR

# Handles require clean tree.
require_clean_tree() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    error "Git working tree is not clean. Commit or stash changes first."
    exit 1
  fi

  if [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    error "Untracked files detected. Commit, remove, or ignore them first."
    exit 1
  fi
}

# Handles require file.
require_file() {
  local file="$1"
  [[ -f "$file" ]] || { error "Required file missing: $file"; exit 1; }
}

# Handles require changelog version.
require_changelog_version() {
  local version="$1"

  if ! grep -Eq "^\## \[${version}\]" "${CHANGELOG_FILE}"; then
    error "${CHANGELOG_FILE} does not appear to contain a section for version ${version}"
    exit 1
  fi
}

# Handles update version file.
update_version_file() {
  local version="$1"
  log_step "Updating VERSION -> ${version}"
  printf '%s\n' "${version}" > "${VERSION_FILE}"
}

# Handles update readme badge.
update_readme_badge() {
  local version="$1"

  if grep -Eq 'badge/version-[0-9]+\.[0-9]+\.[0-9]+' "${README_FILE}"; then
    log_step "Updating README version badge -> ${version}"
    perl -0pi -e "s/badge\/version-[0-9]+\.[0-9]+\.[0-9]+/badge\/version-${version}/g" "${README_FILE}"
  else
    printf 'README version badge not found; skipping\n'
  fi

  if grep -Eq 'releases/tag/v[0-9]+\.[0-9]+\.[0-9]+' "${README_FILE}"; then
    log_step "Updating README release link -> v${version}"
    perl -0pi -e "s/releases\/tag\/v[0-9]+\.[0-9]+\.[0-9]+/releases\/tag\/v${version}/g" "${README_FILE}"
  fi
}

# Bumps the standalone version surfaces release-check validates against VERSION,
# so the state release.sh produces is consistent instead of drifting.
sync_pyproject_version() {
  local version="$1"
  log_step "Syncing ${PYPROJECT_FILE} -> ${version}"
  perl -0pi -e "s/^(version\s*=\s*\")[^\"]+(\")/\${1}${version}\${2}/m" "${PYPROJECT_FILE}"
}

# Replaces only the top-level "version" value; leaves the rest of the JSON as-is.
sync_json_version() {
  local file="$1" version="$2"
  perl -0pi -e "s/(\"version\"\s*:\s*\")[^\"]+(\")/\${1}${version}\${2}/" "${file}"
}

# tool_contracts.json is generated from VERSION (already bumped), not hand-edited.
regenerate_tool_contracts() {
  log_step "Regenerating ${TOOL_CONTRACTS_FILE} from VERSION"
  python3 "${GEN_TOOL_CONTRACTS}" >/dev/null || { error "tool-contracts generation failed"; exit 1; }
}

# Post-bump re-gate. release-check.sh runs BEFORE the bump and validates the old
# state; this runs AFTER and refuses to commit unless every version surface now
# matches VERSION. Silent drift becomes a hard stop instead of a drifted tag.
verify_version_surfaces() {
  local version="$1"
  local ok=true
  check() {
    local label="$1" actual="$2"
    if [[ "$actual" != "$version" ]]; then
      error "${label} is '${actual}', expected '${version}'"
      ok=false
    fi
  }
  check "${PYPROJECT_FILE}" "$(grep '^version' "${PYPROJECT_FILE}" | sed 's/version = "\(.*\)"/\1/')"
  check "${STABILITY_FILE}" "$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "${STABILITY_FILE}")"
  check "${TOOL_CONTRACTS_FILE}" "$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['mq_mcp_version'])" "${TOOL_CONTRACTS_FILE}")"
  check "${CONTRACT_FILE}" "$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "${CONTRACT_FILE}")"
  if ! grep -qF "version-${version}-" "${README_FILE}"; then
    error "README badge does not reference version ${version}"; ok=false
  fi
  if ! grep -qF "releases/tag/v${version}" "${README_FILE}"; then
    error "README release link does not reference v${version}"; ok=false
  fi
  if [[ "$ok" != true ]]; then
    error "Version surfaces are not consistent after bump — aborting"
    exit 1
  fi
  log_step "Verified all version surfaces match VERSION (${version})"
}

# Handles init changelog section.
init_changelog_section() {
  local version="$1"
  local today tmp_file
  today="$(date +%F)"

  require_file "${CHANGELOG_FILE}"

  if grep -Eq "^\## \[${version}\]" "${CHANGELOG_FILE}"; then
    printf 'CHANGELOG already contains version %s\n' "${version}"
    return 0
  fi

  tmp_file="$(mktemp)"

  {
    printf '## [%s] - %s\n\n' "${version}" "${today}"
    printf '### Added\n'
    printf -- '- \n\n'
    printf '### Changed\n'
    printf -- '- \n\n'
    printf '### Fixed\n'
    printf -- '- \n\n'
    cat "${CHANGELOG_FILE}"
  } > "${tmp_file}"

  mv "${tmp_file}" "${CHANGELOG_FILE}"
  printf 'Initialized CHANGELOG.md template for version %s\n' "${version}"
}

# Prints summary.
print_summary() {
  local tag="v${VERSION}"

  cat <<EOF_SUMMARY
Release summary
---------------
Version : ${VERSION}
Tag     : ${tag}
Branch  : main
Files   : ${VERSION_FILE}, ${README_FILE}, ${CHANGELOG_FILE}, ${PYPROJECT_FILE},
          ${STABILITY_FILE}, ${TOOL_CONTRACTS_FILE}, ${CONTRACT_FILE}
GitHub  : $( [[ "${GITHUB_RELEASE}" == true ]] && echo enabled || echo disabled )
EOF_SUMMARY
}

# Handles create release commit and tag.
create_release_commit_and_tag() {
  local version="$1"
  local tag="v${version}"

  git add \
    "${VERSION_FILE}" "${README_FILE}" "${CHANGELOG_FILE}" \
    "${PYPROJECT_FILE}" "${STABILITY_FILE}" "${TOOL_CONTRACTS_FILE}" "${CONTRACT_FILE}"
  git commit -m "Prepare ${tag} release"
  git tag -a "${tag}" -m "${tag}"
}

# Handles push release.
push_release() {
  local version="$1"
  local tag="v${version}"

  git push origin main
  git push origin "${tag}"
}

# Regenerates Command-Reference.md and pushes to the GitHub Wiki.
update_wiki_command_ref() {
  local version="$1"
  local generator="${BASH_SOURCE[0]%/*}/tools/scripts/generate-wiki-command-ref.sh"
  local wiki_tmp
  wiki_tmp="$(mktemp -d)"

  if [[ ! -x "$generator" ]]; then
    printf '[wiki] generator not found, skipping wiki update\n'
    return 0
  fi

  log_step "Updating wiki Command-Reference"

  if ! "$generator" >/dev/null 2>&1; then
    printf '[wiki] generator failed, skipping wiki push\n'
    rm -rf "$wiki_tmp"
    return 0
  fi

  local generated="$HOME/macos-scripts.wiki/Command-Reference.md"
  if [[ ! -f "$generated" ]]; then
    printf '[wiki] Command-Reference.md not found after generation, skipping wiki push\n'
    rm -rf "$wiki_tmp"
    return 0
  fi

  if ! git clone --quiet git@github.com:MCamner/macos-scripts.wiki.git "$wiki_tmp" 2>/dev/null; then
    printf '[wiki] could not clone wiki repo, skipping wiki push\n'
    rm -rf "$wiki_tmp"
    return 0
  fi

  cp "$generated" "$wiki_tmp/Command-Reference.md"
  cd "$wiki_tmp"
  git add Command-Reference.md
  if git diff --cached --quiet; then
    printf '[wiki] Command-Reference unchanged, no push needed\n'
  else
    git commit -m "Update Command-Reference for v${version}"
    git push --quiet
    printf '[wiki] Command-Reference pushed\n'
  fi
  cd - >/dev/null
  rm -rf "$wiki_tmp"
}

# Handles create github release.
create_github_release() {
  local version="$1"
  local tag="v${version}"

  command -v gh >/dev/null 2>&1 || {
    error "gh CLI is required for --github-release"
    exit 1
  }

  gh release create "${tag}" \
    --title "${tag}" \
    --notes-file "${CHANGELOG_FILE}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --github-release)
      GITHUB_RELEASE=true
      shift
      ;;
    --init-changelog)
      INIT_CHANGELOG=true
      shift
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    -*)
      error "Unknown option: $1"
      show_usage
      exit 1
      ;;
    *)
      if [[ -n "${VERSION}" ]]; then
        error "Only one version argument is allowed."
        show_usage
        exit 1
      fi
      VERSION="$1"
      shift
      ;;
  esac
done

if [[ -z "${VERSION}" ]]; then
  show_usage
  printf '\nRelease aborted.\n'
  exit 1
fi

require_file "${VERSION_FILE}"
require_file "${README_FILE}"
require_file "${CHANGELOG_FILE}"
require_file "${PYPROJECT_FILE}"
require_file "${STABILITY_FILE}"
require_file "${TOOL_CONTRACTS_FILE}"
require_file "${CONTRACT_FILE}"
require_file "${GEN_TOOL_CONTRACTS}"

if [[ "${INIT_CHANGELOG}" == true ]]; then
  init_changelog_section "${VERSION}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Pre-flight: run full release-check gate before touching anything
# ---------------------------------------------------------------------------
RELEASE_CHECK="${BASH_SOURCE[0]%/*}/scripts/release-check.sh"
if [[ -x "$RELEASE_CHECK" ]]; then
  log_step "Running release-check gate"
  if [[ "${DRY_RUN}" == true ]]; then
    "$RELEASE_CHECK" --dry-run || { error "Release gate failed — fix issues above."; exit 1; }
  else
    "$RELEASE_CHECK" || { error "Release gate failed — fix issues above."; exit 1; }
  fi
  printf '\n'
else
  error "scripts/release-check.sh missing — cannot verify release readiness"
  exit 1
fi

require_clean_tree

print_summary
printf '\n'

if [[ "${DRY_RUN}" == false ]]; then
  log_step "Syncing with origin/main"
  git fetch origin main
  git checkout main >/dev/null 2>&1 || true
  git pull --ff-only origin main
fi

if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
  error "Tag v${VERSION} already exists locally."
  exit 1
fi

if git ls-remote --tags origin | grep -q "refs/tags/v${VERSION}$"; then
  error "Tag v${VERSION} already exists on origin."
  exit 1
fi

update_version_file "${VERSION}"
update_readme_badge "${VERSION}"
sync_pyproject_version "${VERSION}"
sync_json_version "${STABILITY_FILE}" "${VERSION}"
sync_json_version "${CONTRACT_FILE}" "${VERSION}"
regenerate_tool_contracts

log_step "Verifying CHANGELOG contains version ${VERSION}"
require_changelog_version "${VERSION}"

verify_version_surfaces "${VERSION}"

log_step "Showing diff preview"
git --no-pager diff -- \
  "${VERSION_FILE}" "${README_FILE}" "${CHANGELOG_FILE}" \
  "${PYPROJECT_FILE}" "${STABILITY_FILE}" "${TOOL_CONTRACTS_FILE}" "${CONTRACT_FILE}" || true

if [[ "${DRY_RUN}" == true ]]; then
  printf '\nDry run complete. No commit, tag, or push performed.\n'
  rollback_local_changes
  exit 0
fi

log_step "Creating release commit and tag"
create_release_commit_and_tag "${VERSION}"

log_step "Pushing main and tag"
push_release "${VERSION}"

update_wiki_command_ref "${VERSION}"

if [[ "${GITHUB_RELEASE}" == true ]]; then
  log_step "Creating GitHub release"
  create_github_release "${VERSION}"
fi

trap - ERR
printf '\nRelease completed successfully.\n'
