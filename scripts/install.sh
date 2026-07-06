#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/mq-mcp"
ENV_FILE="$APP/.env"
ENV_EXAMPLE="$APP/.env.example"

printf '== mq-mcp install ==\n'
printf 'repo: %s\n\n' "$ROOT"

command -v uv >/dev/null 2>&1 || {
  printf 'ERROR: uv is required. Install it from https://docs.astral.sh/uv/\n' >&2
  exit 1
}

if [[ ! -f "$ENV_FILE" && -f "$ENV_EXAMPLE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  printf 'Created %s from .env.example\n' "$ENV_FILE"
else
  printf 'Keeping existing %s\n' "$ENV_FILE"
fi

uv --directory "$APP" sync
uv tool install "$APP" --force

printf '\nInstalled mq-mcp command:\n'
printf '  mq-mcp doctor\n'
printf '  mq-mcp tools\n'
printf '  mq-mcp serve\n'
printf '\n'
uv --directory "$APP" run python main.py doctor

if ! command -v mq-mcp >/dev/null 2>&1; then
  printf '\nNOTE: mq-mcp is installed by uv, but its bin directory is not on PATH in this shell yet.\n'
  printf 'Run `uv tool dir --bin` to find the directory to add to PATH.\n'
fi

# --- post-commit learn hook -------------------------------------------------
# Auto-extracts a learn candidate from each commit into the pending inbox
# (never the curated store). Background, best-effort, no-op without Ollama.
HOOK_SRC="$ROOT/scripts/post-commit"
HOOK_DST="$ROOT/.git/hooks/post-commit"
if [[ -d "$ROOT/.git/hooks" && -f "$HOOK_SRC" ]]; then
  if [[ -f "$HOOK_DST" ]] && ! grep -q 'post_commit_learn.py' "$HOOK_DST"; then
    printf '\nNOTE: %s exists and is not the mq-mcp learn hook — leaving it alone.\n' "$HOOK_DST"
  else
    install -m 0755 "$HOOK_SRC" "$HOOK_DST"
    printf '\nInstalled post-commit learn hook: %s\n' "$HOOK_DST"
  fi
fi

# --- bridget launcher -------------------------------------------------------
BIN_DIR="${BIN_DIR:-$HOME/bin}"
mkdir -p "$BIN_DIR"
install -m 0755 "$ROOT/scripts/bridget" "$BIN_DIR/bridget"
printf '\nInstalled bridget launcher: %s\n' "$BIN_DIR/bridget"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf 'NOTE: %s is not on PATH. Add it: export PATH="%s:$PATH"\n' "$BIN_DIR" "$BIN_DIR" ;;
esac

# The goto/CD feature and interactive --do mode need a small zsh wrapper. We do
# not edit ~/.zshrc automatically; add this block once if you do not have it:
if ! grep -q '_bridget()' "${ZDOTDIR:-$HOME}/.zshrc" 2>/dev/null; then
  cat <<'ZSNIPPET'

Add this to your ~/.zshrc to enable the goto/CD feature and interactive --do:

# Coordinates bridget behavior.
  _bridget() {
    # --do is interactive (y/n approval prompts) — run attached to the terminal,
    # without capturing stdout, or the prompt is hidden and the read breaks.
    local a
    for a in "$@"; do
      if [[ "$a" == "--do" ]]; then
        command bridget "$@"
        return
      fi
    done
    local out cd_target
    out=$(command bridget "$@" 2>&1)
    cd_target=$(printf '%s\n' "$out" | grep '^CD:' | head -1)
    if [[ -n "$cd_target" ]]; then
      cd "${cd_target#CD:}" && echo "→ ${cd_target#CD:}"
    else
      printf '%s\n' "$out"
    fi
  }
  alias bridget='_bridget'

ZSNIPPET
fi
