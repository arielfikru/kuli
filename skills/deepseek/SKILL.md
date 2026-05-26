---
name: deepseek
description: Delegate cheap/bulk subtasks to DeepSeek V4 via OpenRouter instead of doing them inline on Claude. Use for research, summarization, drafting, data extraction, bulk transforms, brainstorming, or any well-scoped task where DeepSeek output is good enough and saves Claude tokens/cost. Trigger when user says "pakai deepseek", "delegate to deepseek", "/deepseek", or when a subtask is mechanical enough to offload. Claude stays the orchestrator and validates output.
---

# DeepSeek V4 delegation

Claude = orchestrator/brain. DeepSeek = cheap worker called via CLI. Claude decides
what to delegate, calls the tool, then **validates** the result before using it.

## Tool

`ask-deepseek` (at `~/.claude/bin/ask-deepseek`). Stdlib Python, no deps.
Needs `OPENROUTER_API_KEY` env var.

```bash
# direct prompt
ask-deepseek "summarize the tradeoffs of WAL vs rollback journaling"

# pipe a file / command output for analysis
rtk cat report.md | ask-deepseek "extract every action item as a bullet"
ask-deepseek -f src/big.py "list every public function and its purpose"

# cheaper model for trivial work
ask-deepseek --flash "rewrite this sentence formally: ..."

# system prompt + JSON output (machine-parseable)
ask-deepseek -s "You are a data extractor" --json "return {name,email} from: ..."
```

Flags: `--flash` (v4-flash, cheap), `-m SLUG`, `-s SYSTEM`, `-f FILE`, `-t TEMP`,
`--max-tokens N`, `--json`, `-q` (no usage stats). Models:
`deepseek/deepseek-v4-pro` (default), `deepseek/deepseek-v4-flash`.

## When to delegate (offload to DeepSeek)

- Research / explanation that doesn't need codebase context
- Summarizing long text, logs, docs
- Drafting boilerplate prose, comments, commit-body brainstorm
- Bulk mechanical transforms (reformat, extract, classify many items)
- First-pass brainstorming / option generation

## When NOT to delegate (keep on Claude)

- Anything needing this repo's structure, tools, or graph context
- Editing files, running commands, multi-step orchestration
- Final correctness-critical decisions — Claude reviews DeepSeek output, never
  pastes it blind
- Security-sensitive reasoning

## Pattern

1. Scope the subtask tightly (DeepSeek has no repo context — give it the text).
2. Call `ask-deepseek` via Bash, capture output.
3. Validate / correct, then integrate. Cite that DeepSeek produced the draft.

For batch fan-out, call `ask-deepseek` multiple times in parallel Bash calls.

## Caching (automatic)

DeepSeek prompt caching on OpenRouter is **automatic** — no `cache_control`
breakpoints needed. Cached prompt tokens bill at ~0.25x. Cache keys on the
**prefix** of the request, so to get hits:

- Keep the stable part first and identical across calls: same `-s SYSTEM`, same
  `-f FILE` reference block. Put the varying question last (CLI already orders
  system → file → prompt).
- For batch fan-out over one big document, pass the doc via the same `-f FILE`
  (or identical `-s`) every call so the shared prefix is cached after call 1.

`ask-deepseek` reports cache usage on stderr, e.g.
`[deepseek/deepseek-v4-pro | in 5000 out 200 tok | cached 4800 (~0.25x) | discount $0.0012]`.
