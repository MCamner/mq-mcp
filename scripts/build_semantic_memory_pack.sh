#!/usr/bin/env bash
# Build the cross-repo "semantic repository memory" vector pack.
# Output: /tmp/semantic-memory-pack/  (flat, unique filenames)
#
# Run from anywhere:
#   bash ~/mq-mcp/scripts/build_semantic_memory_pack.sh
set -euo pipefail

HOME_DIR="$HOME"
PACK="/tmp/semantic-memory-pack"
MQ_MCP="$HOME_DIR/mq-mcp"

echo "Building semantic memory pack → $PACK"
echo

rm -rf "$PACK"
mkdir -p "$PACK"

total=0

# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

# Handles add file.
add_file() {
  local repo="$1"   # prefix (e.g. "mq-mcp")
  local src="$2"    # absolute path to file
  local rel="$3"    # relative path inside repo (for naming)

  [[ -f "$src" ]] || return 0

  local safe
  safe="$(echo "$rel" | sed 's#^/##; s#/#__#g')"

  # .toml not supported by OpenAI vector store
  if [[ "$safe" == *.toml ]]; then
    safe="${safe%.toml}.toml.txt"
  fi

  cp "$src" "$PACK/${repo}__${safe}"
  echo "  [$repo] $rel"
  (( total++ )) || true
}

# Handles add glob.
add_glob() {
  local repo="$1"
  local base="$2"   # repo root
  local pattern="$3"

  while IFS= read -r -d '' f; do
    local rel="${f#$base/}"
    add_file "$repo" "$f" "$rel"
  done < <(find "$base" -path "$base/$pattern" -type f -print0 2>/dev/null | sort -z)
}

# -----------------------------------------------------------------
# GLOBAL files
# -----------------------------------------------------------------

echo "--- GLOBAL ---"
for f in \
  "$MQ_MCP/docs/global/GLOBAL_REPO_MAP.md" \
  "$MQ_MCP/docs/global/GLOBAL_COMMAND_SURFACE.md" \
  "$MQ_MCP/docs/global/GLOBAL_ARCHITECTURE_NOTES.md" \
  "$MQ_MCP/docs/global/GLOBAL_VECTOR_STORE_POLICY.md"
do
  [[ -f "$f" ]] || continue
  base="$(basename "$f")"
  cp "$f" "$PACK/$base"
  echo "  [global] $base"
  (( total++ )) || true
done

# -----------------------------------------------------------------
# mqobsidian (durable MQ memory — curated views only, not the whole vault)
# -----------------------------------------------------------------

echo "--- mqobsidian ---"
R="$HOME_DIR/mqobsidian"
for f in \
  home/dashboard.md \
  memory/learn/index.md \
  memory/learn/README.md \
  docs/architecture.md \
  docs/memory-model.md \
  docs/CONTEXT_CONTRACT.md \
  docs/context-export-contract.md \
  docs/agent-entrypoint-lineage.md \
  docs/truth-export.md \
  docs/workflow-observations.md \
  docs/roadmap-token-reduction.md
do
  add_file "mqobsidian" "$R/$f" "$f"
done
# Compressed per-system memory + per-repo agent lesson views (low-token,
# high-value). Deliberately excludes memory/learn/patterns/* raw notes and
# the rest of the vault, per the "prefer views, don't scan the whole vault"
# rule in mqobsidian AGENTS.md.
add_glob "mqobsidian" "$R" "systems/*/index.md"
add_glob "mqobsidian" "$R" "systems/*/hot.md"
add_glob "mqobsidian" "$R" "memory/learn/agent/*.md"

# -----------------------------------------------------------------
# mq-mcp
# -----------------------------------------------------------------

echo "--- mq-mcp ---"
R="$HOME_DIR/mq-mcp"
for f in README.md CHANGELOG.md ROADMAP.md VERSION LICENSE RUNBOOK.md TOOL_INDEX.md VECTOR_CONTEXT.md SAFETY_MODEL.md; do
  add_file "mq-mcp" "$R/$f" "$f"
done
for f in docs/install.md docs/security.md docs/demo.md docs/semantic-index/mcp-tools-map.md docs/semantic-index/architecture.md; do
  add_file "mq-mcp" "$R/$f" "$f"
done
for f in mq-mcp/server.py mq-mcp/bridge.py mq-mcp/ask.py mq-mcp/main.py; do
  add_file "mq-mcp" "$R/$f" "$f"
done
for f in mq-mcp/pyproject.toml scripts/validate.sh tests/test_server_safety.py .github/workflows/validate.yml; do
  add_file "mq-mcp" "$R/$f" "$f"
done

# -----------------------------------------------------------------
# repo-signal
# -----------------------------------------------------------------

echo "--- repo-signal ---"
R="$HOME_DIR/repo-signal"
for f in README.md CHANGELOG.md VERSION LICENSE; do
  add_file "repo-signal" "$R/$f" "$f"
done
add_glob "repo-signal" "$R" "docs/ROADMAP.md"
add_glob "repo-signal" "$R" "docs/wiki-export/*.md"
for f in \
  repo_signal/cli.py \
  repo_signal/analyze.py \
  repo_signal/publish_checklist.py \
  repo_signal/doctor.py \
  repo_signal/readme_score.py \
  repo_signal/semantic_upload.py \
  repo_signal/semantic.py \
  repo_signal/pipeline/ask.py \
  repo_signal/pipeline/context.py \
  repo_signal/repoaware/context_builder.py \
  repo_signal/ai/providers/openai_provider.py \
  repo_signal/core/scanner.py
do
  add_file "repo-signal" "$R/$f" "$f"
done
add_glob "repo-signal" "$R" "skills/*/SKILL.md"
for f in tests/test_cli.py tests/test_publish_checklist.py tests/test_semantic_upload.py; do
  add_file "repo-signal" "$R/$f" "$f"
done
add_glob "repo-signal" "$R" ".github/workflows/*.yml"

# -----------------------------------------------------------------
# macos-scripts
# -----------------------------------------------------------------

echo "--- macos-scripts ---"
R="$HOME_DIR/macos-scripts"
for f in README.md CHANGELOG.md ROADMAP.md VERSION; do
  add_file "macos-scripts" "$R/$f" "$f"
done
for f in \
  terminal/launchers/mqlaunch.sh \
  terminal/launchers/mqlaunch-command-mode.sh \
  terminal/menus/mq-main-menu.sh \
  terminal/menus/mq-help-menu.sh \
  terminal/menus/mq-dev-menu.sh \
  terminal/menus/mq-ai-menu.sh \
  terminal/menus/mq-release-menu.sh \
  terminal/ai-prompts/mq-ai-prompts.sh \
  tools/scripts/doctor.sh \
  tools/scripts/scan.sh \
  tools/cli/ai-mode.sh \
  tools/cli/mq-ui.sh \
  install.sh \
  bootstrap.sh
do
  add_file "macos-scripts" "$R/$f" "$f"
done
add_glob "macos-scripts" "$R" ".github/workflows/*.yml"

# -----------------------------------------------------------------
# atlas-one
# -----------------------------------------------------------------

echo "--- atlas-one ---"
R="$HOME_DIR/atlas-one"
for f in README.md CHANGELOG.md ROADMAP.md VERSION; do
  add_file "atlas-one" "$R/$f" "$f"
done
add_glob "atlas-one" "$R" "docs/*.md"

# -----------------------------------------------------------------
# atlas-loop
# -----------------------------------------------------------------

echo "--- atlas-loop ---"
R="$HOME_DIR/atlas-loop"
for f in README.md CHANGELOG.md VERSION; do
  add_file "atlas-loop" "$R/$f" "$f"
done
for f in cli/atlas-loop.sh; do
  add_file "atlas-loop" "$R/$f" "$f"
done
add_glob "atlas-loop" "$R" "docs/prompts/*.md"
add_glob "atlas-loop" "$R" "skills/*/SKILL.md"
add_glob "atlas-loop" "$R" "examples/*.md"

# -----------------------------------------------------------------
# mcamner-journal
# -----------------------------------------------------------------

echo "--- mcamner-journal ---"
R="$HOME_DIR/mcamner-journal"
for f in README.md CHANGELOG.md ROADMAP.md VERSION; do
  add_file "mcamner-journal" "$R/$f" "$f"
done
add_glob "mcamner-journal" "$R" "docs/knowledge/*.md"

# -----------------------------------------------------------------
# coolThing
# -----------------------------------------------------------------

echo "--- coolThing ---"
R="$HOME_DIR/coolThing"
for f in README.md CHANGELOG.md VERSION; do
  add_file "coolThing" "$R/$f" "$f"
done
for f in backend/app.py; do
  add_file "coolThing" "$R/$f" "$f"
done

# -----------------------------------------------------------------
# zephyr-workbench
# -----------------------------------------------------------------

echo "--- zephyr-workbench ---"
R="$HOME_DIR/zephyr-workbench"
for f in README.md CHANGELOG.md ROADMAP.md VERSION; do
  add_file "zephyr-workbench" "$R/$f" "$f"
done
for f in zephyr/cli.py; do
  add_file "zephyr-workbench" "$R/$f" "$f"
done
add_glob "zephyr-workbench" "$R" "docs/*.md"

# -----------------------------------------------------------------
# Summary
# -----------------------------------------------------------------

echo
echo "Done. $total files in $PACK"
echo
total_bytes=0
find "$PACK" -type f | sort | while read -r f; do
  size="$(wc -c < "$f" | tr -d ' ')"
  printf "  %6d  %s\n" "$size" "$(basename "$f")"
done
echo
echo "Total: $(find "$PACK" -type f | wc -l | tr -d ' ') files"
