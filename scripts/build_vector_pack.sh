#!/usr/bin/env bash
# Build a flat vector pack for the mq-mcp vector store.
# Output: /tmp/mq-mcp-vector-pack/  (flat directory, unique filenames)
#
# Run from repo root:
#   bash scripts/build_vector_pack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK="/tmp/mq-mcp-vector-pack"

ALLOWED_SUFFIXES=".md .txt .py .sh .yml .yaml .html"

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
