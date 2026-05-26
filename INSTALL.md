# Agent install instructions

> **You are an AI coding agent (e.g. Claude Code).** The user told you
> "Install ini https://github.com/arielfikru/kuli". Do exactly the steps below.
> They give you, the agent, a pool of cheap **interns** (KULI — Kana Unified LLM
> Interns) to offload well-scoped subtasks to, while you stay the orchestrator:
>
> - `ask-deepseek` — text / bulk reasoning (DeepSeek V4 via OpenRouter)
> - `ask-gemini` — vision: images & video (Gemini CLI)
> - `ask-codex` — agentic coding: read-only Q&A or `--apply` file edits (Codex)

## Steps

1. **Clone** and run the installer:

   ```bash
   tmp="$(mktemp -d)"
   git clone --depth 1 https://github.com/arielfikru/kuli.git "$tmp"
   bash "$tmp/install.sh"
   ```

   This copies the `kuli` package + `ask-*` launchers into `~/.claude/bin`,
   installs the `/deepseek` `/gemini` `/codex` skills, and adds `~/.claude/bin`
   to PATH.

2. **Auth each intern the user wants** (skip the ones they don't need):

   - deepseek: ask the user for their OpenRouter key, then
     `export OPENROUTER_API_KEY="sk-or-..."` (uncomment the line the installer
     added to `~/.bashrc`). Key at <https://openrouter.ai/keys>. Never commit it.
   - gemini: `gemini login` (OAuth).
   - codex: `codex login` (ChatGPT) or `export OPENAI_API_KEY=...`.

3. **Verify** whichever are set up:

   ```bash
   OPENROUTER_API_KEY="sk-or-..." ask-deepseek --flash "Reply with exactly: PONG"
   ask-gemini "Reply with exactly: PONG"
   ask-codex  "Reply with exactly one word: PONG"
   ```

4. **From now on**, delegate well-scoped subtasks to the right intern instead of
   doing them inline — text/bulk → deepseek, visual → gemini, coding/review →
   codex. Read the matching `~/.claude/skills/<intern>/SKILL.md` for when/how.
   You remain the orchestrator: validate intern output (and review every
   `ask-codex --apply` diff) before using it.

## Optional: MCP server

A single MCP server exposes every intern as a typed tool, so MCP-native agents
can delegate without composing a shell command:

```bash
claude mcp add kuli --env OPENROUTER_API_KEY=sk-or-... -- python3 ~/.claude/mcp/kuli-server.py
```

Tools: `ask_deepseek(_batch)`, `ask_gemini(_batch)`, `ask_codex(_batch)`.

## Notes for the agent

- Subagents always run on your own model; you cannot make a subagent run these
  models. Delegation = calling the `ask-*` CLI via shell (or the MCP tools).
- For "is X implemented?" questions, feed the intern **code** (schema, routers),
  not docs — docs report intent, not reality.
- DeepSeek caching on OpenRouter is automatic (~0.25x cached tokens). Keep the
  stable prefix (`-s`, `-f`) identical across calls for cache hits.
