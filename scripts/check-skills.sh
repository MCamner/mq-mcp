#!/usr/bin/env bash
# Validate agent skills under skills/ and keep SKILLS.md in sync.
#
# Checks:
#   1. frontmatter name matches the skill directory
#   2. every SKILL.md has an "## Evals" section
#   3. skill cross-references ("use `<skill>`") point to existing skills
#   4. backticked file paths in SKILL.md files exist in the repo
#   5. SKILLS.md matches what generate_skills_index() produces from frontmatter
#   6. every skill is discoverable, identically, through both .agents/skills/
#      (Codex) and .claude/skills/ (Claude Code), as a link into skills/ rather
#      than a copy of it
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
  # A path is valid if it exists (relative to repo root or the skill's own
  # directory, so a skill may reference its own assets), or if git ignores it
  # — a generated artifact (e.g. generated/tool-index.json) is absent from a
  # fresh checkout but is a legitimate reference. Only an absent, non-ignored
  # path is a dead reference.
  [[ "$token" =~ ^[A-Za-z0-9._-]+/$ ]] && continue           # bare top-level dir mention (bin/, tools/)
  skill_dir="$(dirname "$file")"
  if [[ ! -e "$token" && ! -e "$skill_dir/$token" ]] && ! git check-ignore -q "$token" 2>/dev/null; then
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

# --- 6: agent discovery parity ----------------------------------------------
#
# Both agents must see the same skill surface. The previous version of this
# check looked at .agents/skills/ only, so a skill that never reached
# .claude/skills/ passed silently -- which is exactly how
# openai-vector-store-refresh came to be invisible to Claude Code from the
# commit that added it.
#
# `if` rather than `[[ ... ]] && ok`, because this script runs under `set -e`:
# the && form returns non-zero when the check failed and aborts the script
# before it can print why.

AGENT_TREES=(.agents/skills .claude/skills)
DISCOVERY_FAIL=0

# 6a: every canonical skill reaches both agents, byte-identical.
for skill_md in skills/*/SKILL.md; do
  name="$(basename "$(dirname "$skill_md")")"
  for tree in "${AGENT_TREES[@]}"; do
    discovered="$tree/$name/SKILL.md"
    if [[ ! -f "$discovered" ]]; then
      fail "$name is not discoverable at $discovered"
      DISCOVERY_FAIL=1
    elif ! cmp -s "$skill_md" "$discovered"; then
      fail "$discovered differs from canonical $skill_md"
      DISCOVERY_FAIL=1
    fi
  done
done

# 6b: every entry is a link into skills/, not a copy and not a second root.
# Comparing content cannot see a copy: it is identical on the day it is made
# and drifts silently afterwards.
for tree in "${AGENT_TREES[@]}"; do
  [[ -d "$tree" ]] || continue
  for entry in "$tree"/*; do
    [[ -e "$entry" || -L "$entry" ]] || continue
    name="$(basename "$entry")"
    expected="../../skills/$name"
    if [[ ! -d "skills/$name" ]]; then
      fail "$tree/$name has no canonical definition at skills/$name/"
      DISCOVERY_FAIL=1
      continue
    fi
    if [[ ! -L "$entry" ]]; then
      fail "$entry is a copy; it must be a symlink to $expected"
      DISCOVERY_FAIL=1
      continue
    fi
    target="$(readlink "$entry")"
    if [[ "$target" != "$expected" ]]; then
      fail "$entry links to '$target'; expected '$expected'"
      DISCOVERY_FAIL=1
    fi
  done
done

if [[ $DISCOVERY_FAIL -eq 0 ]]; then
  ok "agent discovery parity"
fi

if [[ $FAIL -ne 0 ]]; then
  echo "check-skills: FAILED"
  exit 1
fi
echo "check-skills: OK"
