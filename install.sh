#!/usr/bin/env bash
# Installer for KULI — Kana Unified LLM Interns.
# Idempotent: copies the kuli package + launchers + skills into ~/.claude,
# wires PATH, and prints per-intern auth hints.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$CLAUDE_DIR/bin"

echo "==> Installing KULI into $CLAUDE_DIR"
mkdir -p "$BIN" "$CLAUDE_DIR/skills" "$CLAUDE_DIR/mcp"

# Shared package: launchers do `sys.path.insert(0, <their dir>)` then import
# `kuli`, so the package lives right next to them in ~/.claude/bin.
rm -rf "$BIN/kuli"
cp -r "$SRC/kuli" "$BIN/kuli"
find "$BIN/kuli" -name '__pycache__' -type d -prune -exec rm -rf {} +

# Launchers.
for f in "$SRC"/bin/*; do
  install -m 0755 "$f" "$BIN/$(basename "$f")"
done

# Skills (one per intern).
for s in deepseek gemini codex; do
  if [ -f "$SRC/skills/$s/SKILL.md" ]; then
    mkdir -p "$CLAUDE_DIR/skills/$s"
    install -m 0644 "$SRC/skills/$s/SKILL.md" "$CLAUDE_DIR/skills/$s/SKILL.md"
  fi
done

# Optional unified MCP server.
[ -f "$SRC/mcp/server.py" ] && install -m 0644 "$SRC/mcp/server.py" "$CLAUDE_DIR/mcp/kuli-server.py"

# Wire PATH into bash + zsh, once.
add_path() {
  local rc="$1"
  [ -f "$rc" ] || return 0
  grep -q 'claude/bin (kuli)' "$rc" && return 0
  {
    echo ''
    echo '# claude/bin (kuli)'
    echo 'export PATH="$HOME/.claude/bin:$PATH"'
    echo '# export OPENROUTER_API_KEY="sk-or-..."   # <-- for ask-deepseek'
  } >> "$rc"
  echo "==> Added PATH to $rc"
}
add_path "$HOME/.bashrc"
add_path "$HOME/.zshrc"

cat <<'DONE'

Done. Interns installed:
  ask-deepseek  (text/bulk)   skill: /deepseek
  ask-gemini    (vision)      skill: /gemini
  ask-codex     (coding)      skill: /codex
plus their -batch variants.

AUTH per intern:
  deepseek -> export OPENROUTER_API_KEY="sk-or-..."   (https://openrouter.ai/keys)
  gemini   -> run `gemini login`   (OAuth)
  codex    -> run `codex login`    (ChatGPT) or export OPENAI_API_KEY

Test:
  ask-deepseek --flash 'say PONG'
  ask-gemini 'say PONG'
  ask-codex  'reply one word: PONG'
DONE
