#!/usr/bin/env bash
# Build a flat vector pack for the mq-mcp vector store.
# Output: /tmp/mq-mcp-vector-pack/  (flat directory, unique filenames)
#
# Run from repo root:
#   bash scripts/build_vector_pack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK="/tmp/mq-mcp-vector-pack"

ALLOWED_SUFFIXES=".md .txt .py .sh .yml .yaml .html .toml"

SKIP_DIRS=".git .venv __pycache__ .mypy_cache .pytest_cache .ruff_cache node_modules dist build coverage backups .claude"
SKIP_FILES=".env .env.local .envrc uv.lock package-lock.json pnpm-lock.yaml yarn.lock .DS_Store"

# -----------------------------------------------------------------

echo "Building vector pack for: $ROOT"
echo "Output: $PACK"
echo

rm -rf "$PACK"
mkdir -p "$PACK"

# Helper: check if file should be skipped
should_skip() {
  local rel="$1"

  # Skip if any path component is in SKIP_DIRS
  for seg in $(echo "$rel" | tr '/' ' '); do
    for skip in $SKIP_DIRS; do
      [[ "$seg" == "$skip" ]] && return 0
    done
  done

  local base
  base="$(basename "$rel")"

  # Skip exact filenames
  for skip in $SKIP_FILES; do
    [[ "$base" == "$skip" ]] && return 0
  done

  # Skip by suffix
  local ext="${base##*.}"
  [[ "$base" == "$ext" ]] && return 0  # no extension
  local matched=0
  for suf in $ALLOWED_SUFFIXES; do
    [[ ".$ext" == "$suf" ]] && matched=1 && break
  done
  [[ $matched -eq 0 ]] && return 0

  return 1
}

# Helper: flatten path to safe filename
flatten_path() {
  local rel="$1"
  echo "$rel" | sed 's#^\./##; s#/#__#g'
}

# Helper: copy explicit text/context files that do not have uploadable suffixes.
add_context_file() {
  local rel="$1"
  local safe="$2"
  local src="$ROOT/$rel"

  [[ -f "$src" ]] || return 0

  cp "$src" "$PACK/$safe"
  echo "  $rel → $safe"
  (( copied++ )) || true
}

# -----------------------------------------------------------------

copied=0

while IFS= read -r -d '' file; do
  rel="${file#$ROOT/}"

  should_skip "$rel" && continue

  safe="$(flatten_path "$rel")"

  # .toml is not supported by OpenAI — rename to .txt
  if [[ "$safe" == *.toml ]]; then
    safe="${safe%.toml}.toml.txt"
  fi

  cp "$file" "$PACK/$safe"
  echo "  $rel → $safe"
  (( copied++ )) || true
done < <(find "$ROOT" -type f -print0 | sort -z)

# -----------------------------------------------------------------
# Curated text context files

add_context_file ".gitignore" "gitignore.txt"
add_context_file "mq-mcp/.gitignore" "mq-mcp__gitignore.txt"
add_context_file "mq-mcp/.env.example" "mq-mcp__env-example.txt"
add_context_file "VERSION" "VERSION.txt"
add_context_file "LICENSE" "LICENSE.txt"

# -----------------------------------------------------------------
# Generated meta files

{
  echo "# mq-mcp repo tree"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  find "$ROOT" -type f \
    | grep -v '/\.git/' \
    | grep -v '/\.venv/' \
    | grep -v '/__pycache__/' \
    | grep -v '/node_modules/' \
    | grep -v '/dist/' \
    | grep -v '/build/' \
    | grep -v '/backups/' \
    | grep -v '/coverage/' \
    | grep -v '/\.claude/' \
    | sed "s#^$ROOT/##" \
    | sort
} > "$PACK/repo-tree.md"
echo "  [generated] repo-tree.md"

{
  echo "# mq-mcp git context"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## Branch and status"
  echo
  cd "$ROOT" && git status --short --branch
  echo
  echo "## Recent commits"
  echo
  git log --oneline -20
} > "$PACK/git-context.md"
echo "  [generated] git-context.md"
(( copied += 2 )) || true

{
  echo "# mq-mcp entrypoints and commands"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## Primary user commands"
  echo
  echo "- \`bridget \"prompt\"\`: shell wrapper for \`mq-mcp/bridge.py\`; can call MCP tools exposed by \`mq-mcp/server.py\`."
  echo "- \`ask \"prompt\"\`: shell function/client for \`mq-mcp/ask.py\`; answers from OpenAI vector store file search."
  echo "- \`bridget --search \"prompt\"\`: routes to vector-store search via \`ask.py\`."
  echo "- \`./scripts/validate.sh\`: repository validation, safety checks, tool discovery checks, and integration smoke checks."
  echo "- \`uv --directory mq-mcp run mcp run server.py\`: run the local FastMCP server."
  echo "- \`uv --directory mq-mcp run python bridge.py \"List the available MCP tools.\"\`: bridge smoke check."
  echo
  echo "## Vector store maintenance"
  echo
  echo "- \`bash scripts/build_vector_pack.sh\`: rebuilds \`/tmp/mq-mcp-vector-pack\`."
  echo "- \`uv --directory mq-mcp run python ../scripts/upload_vector_pack.py\`: replaces files in the active local vector store."
  echo "- \`python3 scripts/create_vector_store.py\`: creates a new \`mq-mcp-repo-knowledge\` store and uploads the pack."
  echo "- Active local store is read from \`OPENAI_VECTOR_STORE_ID\`."
} > "$PACK/entrypoints-and-commands.md"
echo "  [generated] entrypoints-and-commands.md"
(( copied++ )) || true

{
  echo "# mq-mcp MCP tool contracts"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "Source of truth: \`mq-mcp/server.py\`, \`TOOL_INDEX.md\`, \`docs/TOOL_SAFETY.md\`, and \`docs/semantic-index/mcp-tools-map.md\`."
  echo
  echo "## Default behavior"
  echo
  echo "- Prefer read-only tools for inspection."
  echo "- Use write/execution tools only when the user explicitly asks for an action."
  echo "- Repo file paths are resolved under \`REPO_ROOT\`; external files require explicit allowed roots."
  echo
  echo "## Read-only tools"
  echo
  echo "- \`get_system_resources()\`: returns CPU, memory, and disk summary."
  echo "- \`read_repo_file(relative_path)\`: reads one file inside the repo."
  echo "- \`list_repo_files(max_depth=3)\`: lists repo files, excluding cache/build folders."
  echo "- \`search_repo(query, glob=None)\`: searches repo text with \`git grep -n\`."
  echo "- \`git_status()\`: branch, working tree status, and recent commits."
  echo "- \`git_diff(path=None)\`: current git diff, optionally for one repo path."
  echo "- \`analyze_csv(relative_path)\`: pandas summary for a repo CSV."
  echo "- \`analyze_guitar_pro(relative_path)\`: parses GP3/GP4/GP5 files inside repo or allowed local roots."
  echo "- \`list_local_repos()\`: lists repos registered through \`MQ_MCP_LOCAL_REPOS\` plus mq-mcp."
  echo "- \`tool_safety_report()\`: returns the documented MCP tool safety model."
  echo
  echo "## Write tools"
  echo
  echo "- \`update_repo_file(relative_path, old_text, new_text)\`: exact-match replacement in allowed text/code files. Does not commit."
  echo "- \`edit_image(relative_path, action, value=None)\`: modifies an image in place for supported actions."
  echo
  echo "## Execution tools"
  echo
  echo "- \`validate_project()\`: runs \`scripts/validate.sh\` with timeout."
  echo "- \`run_mqlaunch()\`: opens the interactive launcher in Terminal."
  echo "- \`open_in_app(relative_path)\`: opens a repo or allowed local file with macOS \`open\`."
  echo "- \`open_repo_terminal(repo_name)\`: opens Terminal in a registered repo."
  echo "- \`repo_signal_analyze(repo_name)\` and \`repo_signal_checklist(repo_name)\`: run repo-signal read-only checks for registered repos."
} > "$PACK/tool-contracts.md"
echo "  [generated] tool-contracts.md"
(( copied++ )) || true

{
  echo "# mq-mcp vector store manifest"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## Git"
  echo
  echo "\`\`\`"
  cd "$ROOT" && git status --short --branch
  echo "\`\`\`"
  echo
  echo "## Pack policy"
  echo
  echo "- Include docs, semantic index files, selected source, tests, validation scripts, CI, and generated AI context."
  echo "- Exclude secrets, lock files, caches, virtual environments, logs, backups, binary assets, and local settings."
  echo "- Flatten repo paths with double underscores."
  echo "- Rename unsupported or special context files to \`.txt\` when needed."
  echo
  echo "## Files"
  find "$PACK" -type f -maxdepth 1 | sort | while read -r f; do
    size="$(wc -c < "$f" | tr -d ' ')"
    printf -- "- %s (%s bytes)\n" "$(basename "$f")" "$size"
  done
} > "$PACK/vector-store-manifest.md"
echo "  [generated] vector-store-manifest.md"
(( copied++ )) || true

# -----------------------------------------------------------------

echo
echo "Done. $copied files in $PACK"
echo
find "$PACK" -type f | sort | while read -r f; do
  size="$(wc -c < "$f" | tr -d ' ')"
  printf "  %6d bytes  %s\n" "$size" "$(basename "$f")"
done
echo
total="$(find "$PACK" -type f | wc -l | tr -d ' ')"
echo "Total: $total files"
