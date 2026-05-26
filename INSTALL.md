# Agent install instructions

> **You are an AI coding agent (e.g. Claude Code).** The user told you
> "Install ini https://github.com/arielfikru/claude-use-deepseek". Do exactly
> the steps below. They give you, the agent, a CLI to offload cheap subtasks to
> DeepSeek V4 via OpenRouter while you stay the orchestrator.

## Steps

1. **Clone** the repo to a temp dir and run the installer:

   ```bash
   tmp="$(mktemp -d)"
   git clone --depth 1 https://github.com/arielfikru/claude-use-deepseek.git "$tmp"
   bash "$tmp/install.sh"
   ```

   This copies `ask-deepseek` into `~/.claude/bin`, installs the `/deepseek`
   skill into `~/.claude/skills/deepseek`, and adds `~/.claude/bin` to PATH.

2. **Get the API key.** Ask the user for their OpenRouter API key if not already
   set in `$OPENROUTER_API_KEY`. Tell them to create one at
   <https://openrouter.ai/keys>. Persist it by uncommenting + filling the
   `export OPENROUTER_API_KEY=...` line the installer added to `~/.bashrc`.
   Never commit the key.

3. **Verify** it works:

   ```bash
   OPENROUTER_API_KEY="sk-or-..." ask-deepseek --flash "Reply with exactly: PONG"
   ```

   Expect `PONG` plus a usage line on stderr.

4. **From now on**, delegate well-scoped cheap/bulk subtasks (research,
   summarize, draft, extract, classify) to `ask-deepseek` instead of doing them
   inline. Read `~/.claude/skills/deepseek/SKILL.md` for when/how. You remain the
   orchestrator: validate DeepSeek output before using it.

## Notes for the agent

- Subagents always run on your own model; you cannot make a subagent run
  DeepSeek. Delegation = calling the `ask-deepseek` CLI via shell.
- DeepSeek caching on OpenRouter is automatic (~0.25x cached tokens). Keep the
  stable prefix (`-s SYSTEM`, `-f FILE`) identical across calls for cache hits.
