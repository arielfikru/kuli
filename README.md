# KULI — Kana Unified LLM Interns

Give your AI coding agent (Claude Code) a pool of cheap **interns**. Claude stays
the senior — it scopes the work, hands it to the right intern, then **reviews the
output before anything ships**. KULI bundles three interns behind one consistent
CLI vocabulary and one optional MCP server:

| Intern | CLI | Niche | Backend |
|--------|-----|-------|---------|
| **deepseek** | `ask-deepseek` | cheap text / bulk reasoning | OpenRouter (DeepSeek V4) |
| **or** | `ask-or` | any model — you pick the slug | OpenRouter (any model) |
| **gemini** | `ask-gemini` | vision — sees images & video | Gemini CLI (gemini-3.1-pro) |
| **codex** | `ask-codex` | agentic coding — Q&A or file edits | OpenAI Codex (`codex exec`) |

Each has a `-batch` variant for parallel fan-out. All share one core
(`kuli/core.py`): prompt assembly, self-consistency voting, the stats line, and
batch fan-out are written once and behave identically across interns.

## Why three, not one

They are genuinely different tools, not skins of one model:

- **deepseek** is text-only and cheap — research, summarizing, drafting, bulk
  transforms.
- **gemini** is the only one that can *see* pixels/frames — screenshots, UI bugs,
  video, OCR.
- **codex** reads a real repo and (with `--apply`) edits files in a sandbox —
  code review and scoped implementation.

Different backends, auth, and capabilities — so they stay separate engines under
a shared core, rather than one confused mega-binary.

## Install

```bash
git clone <repo-url> kuli && cd kuli
bash install.sh
```

This copies the `kuli` package + thin launchers into `~/.claude/bin`, installs
the three skills into `~/.claude/skills/`, and wires `~/.claude/bin` onto PATH.

### Auth (per intern)

```bash
export OPENROUTER_API_KEY="sk-or-..."   # deepseek  (https://openrouter.ai/keys)
gemini login                            # gemini    (OAuth)
codex login                             # codex     (ChatGPT) — or export OPENAI_API_KEY
```

### Smoke test

```bash
ask-deepseek --flash 'say PONG'
ask-gemini -f screenshot.png 'what UI bug is visible?'
ask-codex 'reply one word: PONG'
```

## Usage

### deepseek — text / bulk

```bash
ask-deepseek "summarize WAL vs rollback journaling"
ask-deepseek -f report.md "extract every action item as a bullet"
ask-deepseek --flash "rewrite formally: ..."          # cheap model
ask-deepseek -r high "tricky logic problem"           # thinking mode
ask-deepseek -c 5 "Capital of Australia? city only"   # self-consistency vote
printf 'tldr A\ntldr B\n' | ask-deepseek-batch --flash -j 8
```

Flags: `--flash` / `--auto` / `-m`, `-r [high|xhigh]`, `-s SYSTEM`, `-f FILE`,
`-c N`, `--json`, `--show-thinking`, `--timeout`, `-q`.

### or — any OpenRouter model

`ask-or` is the model-agnostic sibling of `ask-deepseek` (same OpenRouter
plumbing). Model is **required** — `-m SLUG` or `OPENROUTER_MODEL` env, no silent
default.

```bash
ask-or -m openai/gpt-5 "review this API design tradeoff: ..."
ask-or -m anthropic/claude-opus-4 -f spec.md "poke holes in this plan"
ask-or -m qwen/qwen3-max "rewrite formally: ..."     # cheap open model
export OPENROUTER_MODEL=openai/gpt-5 && ask-or "quick question"
printf 'tldr A\ntldr B\n' | ask-or-batch -m qwen/qwen3-max -j 8
```

Flags mirror `ask-deepseek` (`-s`, `-f`, `-r`, `-c N`, `--json`, `--timeout`,
`-q`) but with no model preset. Use `/deepseek` for the cheap DeepSeek default;
reach for `ask-or` when you want a specific model or to compare families.

### gemini — vision

```bash
ask-gemini -f shot.png "what UI bug is visible?"
ask-gemini -f clip.mp4 "summarize with timestamps"
ask-gemini -f before.png -f after.png "what changed?"
ask-gemini-batch -p "any layout issue?" shots/*.png -j 8
```

Flags: `-f FILE` (repeatable), `--flash` / `--pro` / `-m`, `-c N`, `--raw`,
`--timeout`, `-q`. Runs from an empty temp dir so each call stays lean (~8k vs
~90k tokens).

### codex — coding (read-only & agentic)

```bash
# read-only (safe): code review / questions about a repo
ask-codex "review the auth middleware for races"
ask-codex -f spec.md "does src/ implement this spec?"

# agentic: edits files — do it in a throwaway worktree, then review the diff
git worktree add ../wt-codex HEAD
ask-codex --apply --cd ../wt-codex "add validation to the season router"
# inspect ../wt-codex diff, keep what's good, remove the worktree

ask-codex-batch --cd apps/api < questions.txt    # read-only fan-out
```

Flags: `--apply` (write mode; default read-only), `--cd DIR`, `-f FILE`,
`-i IMAGE`, `-m`, `-c N` (read-only only), `--timeout`, `--json`, `-q`.
Danger sandbox modes are intentionally not exposed.

## The intern protocol (every call)

1. **Brief** — the intern has no repo memory; bundle what it needs (`-f`, `--cd`).
   For "is X implemented?" feed **code**, not docs — docs report intent, not reality.
2. **Assign** — pick the right intern + cheapest model that works.
3. **Review (mandatory)** — spot-check claims; for `ask-codex --apply`, review
   the diff. Interns hallucinate and overreach — never ship blind.
4. **Integrate** — use the validated result; note it was an intern draft.

## Self-consistency (`-c N`)

Samples N times and majority-votes the answer, printing `agreement V/N` (with
`⚠ LOW` when ≤ half agree). Use only when the answer is a single short verifiable
value and being wrong is costly. Skip for prose/code (every sample differs) or
when you can verify it yourself. It is N× the tokens — never the default.

## Health & fallback

Each `ask-*` records the outcome of its call to a health file. Claude (the
orchestrator) consults it before delegating and drives the fallback — there is
no silent auto-router, so you always know which intern ran.

```bash
kuli health                 # show benched interns (rate-limited / auth-failed) + minutes left
kuli health reset gemini    # after `gemini login`, before a natural success heals it
kuli health reset           # clear all
```

- **rate-limited** → benched until the reset window passes, then self-heals.
- **auth-failed** → benched until a later success or `kuli health reset`.
- **generic errors** → only bench after repeated consecutive failures.

The `/kuli` skill holds the routing policy: which intern for which task, the
fallback ladder (cheaper model → other intern → Claude as last resort), and the
heavy-task → ask / light-task → do-it rule when everything is exhausted.

## MCP (optional)

A single MCP server exposes all interns as typed tools:

```bash
claude mcp add kuli -- python3 /abs/path/to/mcp/server.py
```

Tools: `ask_deepseek`, `ask_deepseek_batch`, `ask_gemini`, `ask_gemini_batch`,
`ask_codex`, `ask_codex_batch`. The CLIs remain the source of truth; the server
only shells out to them.

## Layout

```
kuli/
├── kuli/            # shared package
│   ├── core.py      # voting, stats, batch fan-out, prompt helpers
│   ├── deepseek.py  gemini.py  codex.py          # ask-* adapters
│   └── *_batch.py                                 # ask-*-batch adapters
├── bin/             # thin launchers (import kuli.<mod>:main)
├── skills/          # /deepseek /gemini /codex
├── mcp/server.py    # unified MCP server
└── install.sh
```

Stdlib only — no third-party Python deps (the MCP server needs `mcp` if used).
