---
name: or
description: Delegate a text task to ANY model on OpenRouter via the ask-or CLI — you pick the slug (openai/gpt-…, anthropic/claude-…, google/gemini-…, x-ai/grok-…, qwen/…, meta-llama/…). The flexible, model-agnostic intern. Use when you want a specific model that isn't DeepSeek — a second opinion from a different family, a frontier model for a hard prompt, or a cheap open model for bulk. Trigger when user says "pakai openrouter", "pakai model X", "ask-or", "/or", or names a specific non-DeepSeek model. Claude stays orchestrator and validates output. For DeepSeek specifically use /deepseek; for vision use /gemini; for repo coding use /codex.
---

# OpenRouter delegation — the any-model intern

`ask-or` is the same OpenRouter plumbing as `ask-deepseek`, but **model-agnostic**:
you choose the slug. Treat it as an intern you can swap brains on — pick the
cheapest model that clears the bar, or a frontier model when the task is hard.
Same senior/intern discipline: scope it, hand it the material, **review before
shipping**.

`ask-deepseek` is just the DeepSeek-default preset of this; `ask-or` exposes the
whole OpenRouter catalogue.

## When to reach for ask-or (vs ask-deepseek)

- You want a **specific non-DeepSeek model** (a different family for a second
  opinion, a frontier model for a tricky prompt, a cheap open model for bulk).
- You're **comparing models** on the same prompt.
- Otherwise, for generic cheap text work, `/deepseek` is the simpler default.

## Tool

`ask-or` (at `~/.claude/bin/ask-or`). Stdlib Python. Model is **required** — via
`-m SLUG` or `OPENROUTER_MODEL` env; there is no silent default, so you never
spend on a model you didn't choose. Needs `OPENROUTER_API_KEY`.

```bash
# pick any model explicitly
ask-or -m openai/gpt-5 "review this API design tradeoff: ..."
ask-or -m anthropic/claude-opus-4 -f spec.md "poke holes in this plan"
ask-or -m google/gemini-3-pro "summarize: ..."

# cheap open model for bulk
ask-or -m qwen/qwen3-max "rewrite formally: ..."

# set a default once, then omit -m
export OPENROUTER_MODEL=openai/gpt-5
ask-or "quick question"

# thinking mode (if the model supports it) + self-consistency vote
ask-or -m openai/gpt-5 -r high "hard logic problem"
ask-or -m google/gemini-3-pro -c 5 "Capital of Australia? city only"

# fan out one model over many prompts (shared cached prefix)
printf 'tldr A\ntldr B\n' | ask-or-batch -m qwen/qwen3-max -j 8
```

Flags: `-m SLUG` (or env `OPENROUTER_MODEL`; required), `-s SYSTEM`, `-f FILE`,
`-r [high|xhigh]` (thinking mode, if supported), `-c N` (self-consistency vote),
`-t TEMP`, `--max-tokens N` (env `OPENROUTER_MAX_TOKENS`), `--json`,
`--show-thinking`, `--timeout SEC` (env `OPENROUTER_TIMEOUT`), `-q`.
`ask-or-batch` adds `-d DELIM`, `-j N`; keep `-s`/`-c` identical for cache hits.

## Agentic coding mode (`--agentic`)

`--agentic` drives your chosen model through the **Codex harness** (reads/edits a
repo) — agentic coding on ANY OpenRouter model, no ChatGPT login. Internally
shells `ask-codex --or-model <your -m slug>`.

```bash
ask-or -m anthropic/claude-opus-4 --agentic --apply -C ../wt "refactor X"
ask-or -m qwen/qwen3-max --agentic "review this repo's error handling"  # read-only
```

`--apply` edits files (use a throwaway worktree + review the diff); `--cd DIR` =
root. Token-heavy (codex harness overhead). Tool-use reliability varies by model —
stronger models drive the agent better.

## The intern protocol (same as the others)

1. **Brief** — the intern has no repo memory; bundle context with `-f`. For "is
   X implemented?" feed code, not docs.
2. **Assign** — pick the model: cheap/open for bulk, frontier for hard prompts.
3. **Review (mandatory)** — spot-check; models hallucinate. Use `-c N` only for
   short verifiable answers.
4. **Integrate** — use the validated result; say which model produced it.

## When NOT to use

- DeepSeek specifically is fine → `/deepseek` (simpler, cheap default).
- Image/video → `/gemini`. Repo coding/edits → `/codex`.
- Final correctness calls → Claude, never blind.

## Notes

- Same OpenRouter account/key as deepseek. Caching is automatic (~0.25x cached).
- Pricing varies wildly by model — frontier slugs cost much more than DeepSeek.
  Match the model to the task.
- Related: [[reference-deepseek-delegation]], the gemini and codex skills — one
  KULI worker pool, same review discipline.
