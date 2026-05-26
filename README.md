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
ask-deepseek --auto "route me by size"                # small->flash, large->pro
ask-deepseek -s "You are a data extractor" --json "return {name,email} from: ..."
```

| Flag | Meaning |
| ---- | ------- |
| `--flash` | use `deepseek/deepseek-v4-flash` (cheaper) instead of `-pro` |
| `-m SLUG` | explicit OpenRouter model slug |
| `-s TEXT` | system prompt |
| `-f FILE` | prepend file contents to the prompt |
| `-t N` | temperature (default 0.7) |
| `--max-tokens N` | max **output** tokens (default 262144, env `DEEPSEEK_MAX_TOKENS`) |
| `--json` | request a JSON object response |
| `-q` | suppress the usage/cost line on stderr |

Models: `deepseek/deepseek-v4-pro` (default), `deepseek/deepseek-v4-flash`.
Override the default via `DEEPSEEK_MODEL` env var.

> **Context vs output:** DeepSeek V4 has a **1M-token context window** — that's
> the *input* budget, so you can feed huge files via `-f`. `--max-tokens` caps
> only the **generated output** (default 262144). The cap is just a ceiling — the
> model bills every token it actually generates, so the default rarely matters
> unless a prompt makes the model produce a very long answer. Lower it
> (`--max-tokens 8192` or `DEEPSEEK_MAX_TOKENS`) to hard-limit cost.

## Auto-routing

`--auto` picks the model by estimated input size: small/simple prompts go to
`flash` (cheap), large ones to `pro` (capable). Threshold is `1500` estimated
tokens, override via `DEEPSEEK_AUTO_THRESHOLD`.

```bash
ask-deepseek --auto "Say hi"            # -> v4-flash
ask-deepseek --auto -f huge_doc.md "analyze"   # -> v4-pro
```

## Batch fan-out

`ask-deepseek-batch` runs many prompts in parallel, reusing one cached prefix
(shared `--system`/`--context`), so cost drops after the first call.

```bash
# one prompt per line on stdin
printf 'tldr A\ntldr B\ntldr C\n' | ask-deepseek-batch --flash -j 8

# shared context file (cached), auto-route each question
ask-deepseek-batch -c report.md --auto < questions.txt

# multiline prompts split on a delimiter line, JSON output
ask-deepseek-batch -d '---' --json < prompts.txt > out.json
```

| Flag | Meaning |
| ---- | ------- |
| `-s TEXT` | shared system prompt (cached prefix) |
| `-c FILE` | shared context file (cached prefix) |
| `-d STR` | split prompts on this delimiter line (default: one per line) |
| `-j N` | parallel workers (default 4) |
| `--flash` / `--auto` / `-m` / `-t` / `--max-tokens` | applied to every prompt |
| `--json` | emit a JSON array of `{index, prompt, output, ok}` |

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
