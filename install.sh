#!/usr/bin/env bash
# Installer for claude-use-deepseek.
# Idempotent: copies the CLI + skill into ~/.claude, wires PATH, sets up the key.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing ask-deepseek into $CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR/bin" "$CLAUDE_DIR/skills/deepseek"

install -m 0755 "$SRC/bin/ask-deepseek.py" "$CLAUDE_DIR/bin/ask-deepseek.py"
ln -sf "$CLAUDE_DIR/bin/ask-deepseek.py" "$CLAUDE_DIR/bin/ask-deepseek"
install -m 0644 "$SRC/skills/deepseek/SKILL.md" "$CLAUDE_DIR/skills/deepseek/SKILL.md"

# Wire PATH into the user's shell rc (bash + zsh), once.
add_path() {
  local rc="$1"
  [ -f "$rc" ] || return 0
  grep -q 'claude/bin (ask-deepseek)' "$rc" && return 0
  {
    echo ''
    echo '# claude/bin (ask-deepseek)'
    echo 'export PATH="$HOME/.claude/bin:$PATH"'
    echo '# export OPENROUTER_API_KEY="sk-or-..."   # <-- paste your OpenRouter key'
  } >> "$rc"
  echo "==> Added PATH to $rc"
}
add_path "$HOME/.bashrc"
add_path "$HOME/.zshrc"

echo ""
echo "Done. CLI: $CLAUDE_DIR/bin/ask-deepseek   Skill: /deepseek"
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo ""
  echo "NEXT: set your OpenRouter key (get one at https://openrouter.ai/keys):"
  echo '  export OPENROUTER_API_KEY="sk-or-..."'
  echo "  (uncomment the line just added to your ~/.bashrc to persist it)"
fi
echo ""
echo "Test:  OPENROUTER_API_KEY=sk-or-... ask-deepseek --flash 'say PONG'"
