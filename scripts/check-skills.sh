#!/usr/bin/env bash
# Validate agent skills under skills/ and keep SKILLS.md in sync.
#
# Checks:
#   1. frontmatter name matches the skill directory
#   2. every SKILL.md has an "## Evals" section
#   3. skill cross-references ("use `<skill>`") point to existing skills
#   4. backticked file paths in SKILL.md files exist in the repo
#   5. SKILLS.md matches what generate_skills_index() produces from frontmatter
#
# Usage:
#   ./scripts/check-skills.sh          # check only
#   ./scripts/check-skills.sh --fix    # regenerate SKILLS.md from frontmatter

set -euo pipefail
cd "$(dirname "$0")/.."

FAIL=0
fail() { echo "FAIL: $1"; FAIL=1; }
ok()   { echo "PASS: $1"; }

frontmatter_field() {
  awk -v key="$2" -F': ' '$1 == key { sub("^" key ": ", ""); print; exit }' "$1"
}

# --- 1 + 2: frontmatter and Evals ------------------------------------------

for skill_md in skills/*/SKILL.md; do
  dir_name="$(basename "$(dirname "$skill_md")")"
  fm_name="$(frontmatter_field "$skill_md" name)"
  fm_desc="$(frontmatter_field "$skill_md" description)"

  if [[ "$fm_name" != "$dir_name" ]]; then
    fail "$skill_md frontmatter name '$fm_name' != directory '$dir_name'"
  fi
  if [[ -z "$fm_desc" ]]; then
    fail "$skill_md has no description in frontmatter"
  fi
  if [[ "$fm_name" == \"* || "$fm_desc" == \"* ]]; then
    fail "$skill_md frontmatter uses quoted values; keep them unquoted"
  fi
  if ! grep -q '^## Evals' "$skill_md"; then
    fail "$skill_md is missing an '## Evals' section"
  fi
done
[[ $FAIL -eq 0 ]] && ok "frontmatter and Evals sections"

# --- 3: skill cross-references ----------------------------------------------

REF_FAIL=0
while IFS=: read -r file ref; do
  ref="${ref#use \`}"; ref="${ref%\`}"
  if [[ ! -d "skills/$ref" ]]; then
    fail "$file references non-existent skill '$ref'"
    REF_FAIL=1
  fi
done < <(grep -HoE 'use `[a-z][a-z-]+`' skills/*/SKILL.md)
[[ $REF_FAIL -eq 0 ]] && ok "skill cross-references"

# --- 4: backticked paths exist ----------------------------------------------

PATH_FAIL=0
while IFS=: read -r file token; do
  token="${token#\`}"; token="${token%\`}"
  [[ "$token" == *"*"* || "$token" == *" "* ]] && continue   # globs, phrases
  [[ "$token" == -* || "$token" == /* || "$token" == .* ]] && continue
  if [[ ! -e "$token" ]]; then
    fail "$file references missing path '$token'"
    PATH_FAIL=1
  fi
done < <(grep -HoE '`[A-Za-z][A-Za-z0-9._/-]*/[A-Za-z0-9._/*-]*`' skills/*/SKILL.md)
[[ $PATH_FAIL -eq 0 ]] && ok "referenced paths exist"

# --- 5: SKILLS.md generated from frontmatter ---------------------------------

generate_skills_index() {
  cat <<'HEADER'
# Skills

mq-mcp ships local skills for maintaining the central cognition runtime, MCP
tool surface, semantic memory, learning engine, second brain, integration docs
and release readiness.

Note on namespaces: `skills/` holds agent skills (this index), while
`reviews/skills/` holds review-engine skills consumed by the review runtime.
They are unrelated surfaces that happen to share a name.

This file is generated from SKILL.md frontmatter by
`./scripts/check-skills.sh --fix`. Do not edit the table by hand.

## Built-in skills

| Skill | Description |
| ----- | ----------- |
HEADER
  for skill_md in skills/*/SKILL.md; do
    local name desc
    name="$(basename "$(dirname "$skill_md")")"
    desc="$(frontmatter_field "$skill_md" description)"
    echo "| [$name](skills/$name/SKILL.md) | $desc |"
  done
}

if [[ "${1:-}" == "--fix" ]]; then
  generate_skills_index > SKILLS.md
  ok "SKILLS.md regenerated"
elif ! diff -q <(generate_skills_index) SKILLS.md >/dev/null 2>&1; then
  fail "SKILLS.md is out of sync with skill frontmatter; run ./scripts/check-skills.sh --fix"
else
  ok "SKILLS.md matches skill frontmatter"
fi

if [[ $FAIL -ne 0 ]]; then
  echo "check-skills: FAILED"
  exit 1
fi
echo "check-skills: OK"
