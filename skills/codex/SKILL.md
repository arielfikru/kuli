---
name: codex
description: Delegate coding tasks to OpenAI Codex (codex exec) via the ask-codex CLI. Two modes — read-only (code review, "how does X work", second opinions; safe, no writes) and --apply (agentic: edits files + runs commands in a sandbox). Use when you want a strong code-reasoning second opinion, or to hand off a well-scoped coding task. Trigger when the user says "pakai codex", "tanya codex", "/codex", or when a coding subtask is worth offloading. Claude stays the orchestrator and reviews every diff. NOT for non-code prose (use deepseek) or image/video (use gemini).
---

# Codex delegation — the agentic coding intern

Claude = orchestrator/brain. Codex = the **coding intern**: strong at reading a
repo and reasoning about code, and (in `--apply` mode) at editing files itself.
You scope the work, hand it the task, then **review its output — and its diff —
before keeping anything**. Codex is the one intern that can mutate the
filesystem, so the review gate matters most here.

Two modes, picked by intent:

| Mode | Flag | Sandbox | Use for |
|------|------|---------|---------|
| read-only | *(default)* | `read-only` | code review, "how does X work", second opinion, audits — **no writes** |
| agentic | `--apply` | `workspace-write` | implementing a scoped change, refactor, fix — **edits files** |

## The intern protocol

1. **Brief** — state the task precisely. Unlike deepseek/gemini, codex *does*
   read the repo itself — point it with `--cd DIR` (default cwd). Add context
   docs with `-f FILE` (prepended to the prompt) and images with `-i`.
2. **Assign** — default read-only for questions; `--apply` only when you want
   edits. Pick model with `-m` / `CODEX_MODEL` env.
3. **Review (mandatory gate)** — read the answer; for `--apply`, **review the
   git diff** before keeping it. Codex hallucinates and overreaches.
4. **Integrate** — use the validated result; say codex produced the draft/diff
   you reviewed.

## Safety rules for `--apply` (it edits files)

`--apply` mutates the working tree. Treat it like any irreversible action:

- **Run it in a throwaway git worktree, never the live tree or main branch.**
  e.g. `git worktree add ../wt-codex` then `ask-codex --apply --cd ../wt-codex
  "..."`. Inspect the diff, cherry-pick what's good, delete the worktree.
- **Review the diff before merging — never merge codex's work blind.** Same
  rule as a junior dev's PR.
- **Never push or commit** codex's changes without the user's OK.
- The wrapper deliberately does **not** expose `danger-full-access` or the
  approval/sandbox bypass — don't try to route around it.
- `--consistency` is rejected with `--apply` (would run N parallel mutations).

## Tool

`ask-codex` (at `~/.claude/bin/ask-codex`). Wraps `codex exec`. Stdlib Python.

```bash
# read-only: ask about the repo (safe, no writes)
ask-codex "what does the auth middleware do, and any races?"
ask-codex -f spec.md "does src/ implement everything in this spec?"
ask-codex --cd apps/api "review the episode upload flow for bugs"

# read-only with self-consistency vote (short verifiable answers)
ask-codex -c 3 "does this repo use optimistic locking anywhere? yes/no on last line"

# AGENTIC: let codex edit files — do this in a throwaway worktree
git worktree add ../wt-codex HEAD
ask-codex --apply --cd ../wt-codex "add input validation to the season router"
# then: review the diff in ../wt-codex, keep what's good, remove the worktree

# raw JSONL event stream (debugging)
ask-codex --json "explain main.ts"
```

Flags: `--apply` (agentic write mode; default read-only), `--cd/-C DIR`
(working root), `-f FILE` (prepend file to prompt), `-i IMAGE` (repeatable),
`-m MODEL` / env `CODEX_MODEL`, `-c/--consistency N` (read-only only; sample N,
majority-vote — best for short/factual answers), `--timeout SEC` (default 600,
env `CODEX_TIMEOUT`; raise for big agentic runs), `--json` (raw codex JSONL),
`-q` (no stats). Read-only mode runs `--ephemeral --skip-git-repo-check` so it
works anywhere without littering sessions.

### Run the harness on a non-OpenAI model (`--or-model`)

Codex's agentic harness can drive **any OpenRouter model** instead of native
GPT-5.5 — so you get codex's tool-use/sandbox/worktree machinery on a cheap model,
with **no ChatGPT login** (uses `OPENROUTER_API_KEY`, Responses API).

```bash
ask-codex --or-model deepseek/deepseek-v4-pro --apply -C ../wt "implement X"
ask-codex --or-model anthropic/claude-opus-4 "review this repo"   # read-only
```

This is the engine behind `ask-deepseek --agentic` and `ask-or --agentic`. Use it
when ChatGPT quota is out or you want a specific/cheaper brain in the harness.
Caveats: token-heavy (codex system prompt + tool schema); tool-use reliability
varies by model (use a `-pro`/frontier slug for `--apply`, not a tiny one).

### Batch fan-out (read-only only)

`ask-codex-batch` fans out many **read-only** questions in parallel (no
`--apply` — batching file mutations would race on one tree).

```bash
printf 'audit auth\naudit db layer\naudit routers\n' | ask-codex-batch --cd apps/api -j 3
ask-codex-batch -d '---' --json < questions.txt > out.json
```

Batch flags: `-C/--cd DIR`, `-d DELIM`, `-j N` (workers, def 4), `-m MODEL`,
`--timeout SEC`, `--json`.

## When to delegate to Codex

- Code review / second opinion on a diff, function, or module
- "How does X work / where is Y handled" across a real repo (codex reads it)
- Scoped implementation in a worktree you'll review (`--apply`)
- Auditing for a specific bug class (races, injection, missing validation)

## When NOT to delegate

- Non-code prose, summaries, research → DeepSeek (`/deepseek`), cheaper.
- Image/video/visual reads → Gemini (`/gemini`).
- The final correctness call and the merge decision → **Claude**, never blind.
- Anything you'd not let a junior dev merge unreviewed.

## Notes

- Auth: `codex login` (ChatGPT) or `OPENAI_API_KEY`. A `401
  token_invalidated` means re-run `codex login`.
- Related: [[reference-deepseek-delegation]] (text intern), the gemini skill
  (vision intern) — same senior/intern review discipline across all three KULI
  interns.
