#!/usr/bin/env bash
# Uninstaller for KULI — Kana Unified LLM Interns. Reverses install.sh.
# Removes the package, launchers, skills, and MCP server from ~/.claude and
# strips the PATH block from shell rc files. Idempotent.
#   bash uninstall.sh           # remove code + config
#   bash uninstall.sh --purge   # also delete runtime data (~/.claude/kuli health file)
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$CLAUDE_DIR/bin"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

echo "==> Uninstalling KULI from $CLAUDE_DIR"

# Shared package.
rm -rf "$CLAUDE_DIR/lib/kuli"

# Launchers — remove exactly the ones this repo installs.
if [ -d "$SRC/bin" ]; then
  for f in "$SRC"/bin/*; do
    rm -f "$BIN/$(basename "$f")"
  done
fi

# Skills.
for s in kuli deepseek or gemini codex recraft; do
  rm -f "$CLAUDE_DIR/skills/$s/SKILL.md"
  rmdir "$CLAUDE_DIR/skills/$s" 2>/dev/null || true
done

# MCP server.
rm -f "$CLAUDE_DIR/mcp/kuli-server.py"

# Strip the PATH block from rc files — only if it matches what install.sh wrote
# verbatim, so a key the user pasted into the hint line is never clobbered.
strip_path() {
  local rc="$1"
  [ -f "$rc" ] || return 0
  grep -q 'claude/bin (kuli)' "$rc" || return 0
  CLAUDE_RC="$rc" python3 - <<'PY'
import os
rc = os.environ["CLAUDE_RC"]
block = (
    '\n# claude/bin (kuli)\n'
    'export PATH="$HOME/.claude/bin:$PATH"\n'
    '# export OPENROUTER_API_KEY="sk-or-..."   # <-- for ask-deepseek\n'
)
text = open(rc, encoding="utf-8").read()
if block in text:
    open(rc, "w", encoding="utf-8").write(text.replace(block, "", 1))
    print(f"==> Removed PATH block from {rc}")
else:
    print(f"!! PATH block in {rc} was edited — remove the 'claude/bin (kuli)' lines by hand")
PY
}
strip_path "$HOME/.bashrc"
strip_path "$HOME/.zshrc"

if [ "$PURGE" -eq 1 ]; then
  rm -rf "$CLAUDE_DIR/kuli"
  echo "==> Purged runtime data ($CLAUDE_DIR/kuli)"
fi

cat <<'DONE'

Done. KULI removed.
If you registered the MCP server, also run:  claude mcp remove kuli
Restart your shell (or re-source the rc) to drop ~/.claude/bin from PATH.
Runtime health data kept unless you passed --purge.
DONE
