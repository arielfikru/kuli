---
name: deepseek
description: Delegate cheap/bulk subtasks to DeepSeek V4 via OpenRouter instead of doing them inline on Claude. Use for research, summarization, drafting, data extraction, bulk transforms, brainstorming, or any well-scoped task where DeepSeek output is good enough and saves Claude tokens/cost. Trigger when user says "pakai deepseek", "delegate to deepseek", "/deepseek", or when a subtask is mechanical enough to offload. Claude stays the orchestrator and validates output.
---

# DeepSeek V4 delegation — the "intern" model

Treat DeepSeek as a **cheap, capable intern working under you (Claude)**. You are
the senior: you scope the work, hand the intern everything it needs (it has no
memory of the repo), let it grind, then **review its output before anything ships**.
You never merge the intern's work blind, and you escalate hard/critical decisions
to yourself.

The intern protocol — every delegation follows it:

1. **Brief** — state the task precisely. The intern has zero repo context, so
   bundle the material it needs into `-f FILE` / stdin (file tree, key files, the
   text to transform). A vague brief gets vague work.
2. **Assign** — pick the right intern for the job:
   - trivial / bulk / mechanical → `--flash` (cheapest)
   - sized automatically → `--auto`
   - needs to *think hard* (math, logic, tricky analysis) → `--reasoning` /
     `--reasoning xhigh` (thinking mode; measurably more accurate)
   - many similar items → `ask-deepseek-batch` (parallel, shared cached prefix)
   - **answer is a single short verifiable value AND being wrong is costly**
     (a number, name, yes/no, classification, picked option) → add `-c 5`
     (self-consistency vote). Decision rule:
     - USE `-c` when: factual/numeric/categorical answer + you'd otherwise have to
       trust it blind (no cheap way to verify). The `agreement X/N` line tells you
       how much to trust it; `⚠ LOW` = don't.
     - SKIP `-c` when: output is prose/code/a draft (every sample differs, vote is
       meaningless), OR you can verify the result yourself anyway (run it, check
       the repo), OR cost matters more than the extra confidence. It is N× the
       tokens — never the default.
3. **Review (mandatory gate)** — read the output, spot-check claims against the
   real repo/source, correct mistakes. The intern hallucinates and overstates;
   never paste its result into user-facing work without verifying.
4. **Integrate** — use the validated result, and say it was an intern draft you
   reviewed.

### Protect your own context (token discipline)

Delegating already saves *your* input tokens — the intern reads the big file, you
don't. But the intern's **output** lands back in your context when you read the
command result. For large outputs, don't slurp it all:

- Redirect to a file, then read only the slice you need:
  ```bash
  ask-deepseek -f bigdoc.md "produce a detailed report" > /tmp/ds_out.md
  ```
  Then `Read /tmp/ds_out.md` with `limit`/`offset`, or `grep` for the part that
  matters — instead of piping the whole thing through your context.
- Make the intern do the trimming: ask for a tight format up front ("max 200
  words", "bullets only", "return just the JSON"). Cheaper to constrain the
  intern than to ingest verbosity and summarize it yourself.
- Use `-q` to drop the stderr stats line when you don't need cost numbers.

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

# make the intern think hard (thinking mode) for a tricky problem
ask-deepseek -r high "logic/math problem ..."        # or -r xhigh for max effort

# self-consistency: sample 5, majority-vote, flag disagreement (short answers)
ask-deepseek --flash -c 5 "Capital of Australia? Reply ONLY the city."

# system prompt + JSON output (machine-parseable)
ask-deepseek -s "You are a data extractor" --json "return {name,email} from: ..."
```

Flags: `--flash` (v4-flash, cheap), `--auto` (route by input size: small→flash,
large→pro; threshold `DEEPSEEK_AUTO_THRESHOLD` tokens, default 1500),
`--reasoning/-r [high|xhigh]` (thinking mode — bare = high; big accuracy gain on
hard reasoning, costs more output tokens), `-m SLUG`, `-s SYSTEM`, `-f FILE`,
`--consistency/-c N` (automatic review gate: sample N, majority-vote the answer,
print `agreement X/N` + `⚠ LOW` when no majority — best for short/factual/numeric
answers, not long prose), `-t TEMP`, `--max-tokens N` (output cap, default 262144,
env `DEEPSEEK_MAX_TOKENS`), `--show-thinking` (print the reasoning process too,
not just the final answer — off by default), `--timeout SEC` (default 600, env
`DEEPSEEK_TIMEOUT`; raise for long `xhigh` runs), `--json`, `-q` (no stats). Models:
`deepseek/deepseek-v4-pro` (default), `deepseek/deepseek-v4-flash`. Context
window is 1M tokens (input) — feed big files via `-f`; output is capped by
`--max-tokens`, not 1M.

### Batch fan-out

`ask-deepseek-batch` sends many prompts in parallel, reusing one cached prefix:

```bash
# one prompt per line on stdin
printf 'tldr A\ntldr B\ntldr C\n' | ask-deepseek-batch --flash -j 8

# shared context file -> cached after first call; --auto routes each
ask-deepseek-batch -c report.md --auto < questions.txt

# multiline prompts split on a delimiter line; JSON output
ask-deepseek-batch -d '---' --json < prompts.txt > out.json
```

Batch flags: `-s SYSTEM`, `-c CONTEXT_FILE`, `-d DELIM`, `-j N` (workers, def 4),
`--flash`, `--auto`, `-m`, `-t`, `--max-tokens`, `--json`. Use it for fan-out over
a big document — keep `-s`/`-c` identical so the shared prefix is cached.

## When to delegate (offload to DeepSeek)

- Research / explanation that doesn't need codebase context
- Summarizing long text, logs, docs
- Drafting boilerplate prose, comments, commit-body brainstorm
- Bulk mechanical transforms (reformat, extract, classify many items)
- First-pass brainstorming / option generation

## Escalate to yourself — do NOT hand the intern (keep on Claude)

- Anything needing this repo's structure, tools, or graph context
- Editing files, running commands, multi-step orchestration
- Final correctness-critical decisions — you review the intern's output, never
  ship it blind
- Security-sensitive reasoning

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
