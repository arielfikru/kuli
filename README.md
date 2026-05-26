# claude-use-deepseek

Give your AI coding agent (Claude Code) a second brain: offload cheap, bulk, or
well-scoped subtasks to **DeepSeek V4** via [OpenRouter](https://openrouter.ai),
while the agent stays the orchestrator and validates results.

The agent keeps full reasoning; DeepSeek does the grunt work (research,
summarizing, drafting, extraction, classification, brainstorming) at a fraction
of the cost. OpenRouter prompt caching is automatic (~0.25x for cached tokens).

## Install — just tell your agent

Paste this to Claude Code (or any agent that can run shell + clone repos):

```
Install ini https://github.com/arielfikru/claude-use-deepseek
```

The agent reads [`INSTALL.md`](INSTALL.md) and sets itself up. That's it.

### Manual install

```bash
git clone --depth 1 https://github.com/arielfikru/claude-use-deepseek.git
bash claude-use-deepseek/install.sh
export OPENROUTER_API_KEY="sk-or-..."   # get one at https://openrouter.ai/keys
ask-deepseek --flash "Reply with exactly: PONG"
```

## What gets installed

| Path | What |
| ---- | ---- |
| `~/.claude/bin/ask-deepseek` | the CLI (stdlib Python, zero deps) |
| `~/.claude/skills/deepseek/SKILL.md` | the `/deepseek` skill: when/how the agent delegates |
| `~/.bashrc` (+`~/.zshrc`) | adds `~/.claude/bin` to PATH, key placeholder |

## CLI usage

```bash
ask-deepseek "summarize the tradeoffs of WAL vs rollback journaling"
cat report.md | ask-deepseek "extract every action item as a bullet"
ask-deepseek -f src/big.py "list every public function and its purpose"
ask-deepseek --flash "cheap quick task"               # v4-flash instead of v4-pro
ask-deepseek -s "You are a data extractor" --json "return {name,email} from: ..."
```

| Flag | Meaning |
| ---- | ------- |
| `--flash` | use `deepseek/deepseek-v4-flash` (cheaper) instead of `-pro` |
| `-m SLUG` | explicit OpenRouter model slug |
| `-s TEXT` | system prompt |
| `-f FILE` | prepend file contents to the prompt |
| `-t N` | temperature (default 0.7) |
| `--max-tokens N` | max output tokens (default 4096) |
| `--json` | request a JSON object response |
| `-q` | suppress the usage/cost line on stderr |

Models: `deepseek/deepseek-v4-pro` (default), `deepseek/deepseek-v4-flash`.
Override the default via `DEEPSEEK_MODEL` env var.

## Caching

DeepSeek caching on OpenRouter is automatic — no `cache_control` breakpoints.
Cached prompt tokens bill at ~0.25x. The cache keys on the request **prefix**, so
keep the stable part (same `-s SYSTEM` / `-f FILE`) identical and put the varying
question last (the CLI already orders system → file → prompt). The usage line
reports cache hits:

```
[deepseek/deepseek-v4-flash | in 1213 out 39 tok | cached 509 (~0.25x)]
```

## Requirements

- Python 3.8+ (stdlib only — no pip installs)
- An OpenRouter API key
- Optional: Claude Code, for the `/deepseek` skill auto-trigger

## License

MIT
