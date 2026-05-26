---
name: kuli
description: Orchestration policy for the KULI intern pool — how Claude routes work across the interns (deepseek, or, gemini, codex, recraft), falls back when one is rate-limited or logged out, and decides when to stop and ask vs do it itself. Read this whenever you are about to delegate to any ask-* CLI, are choosing between interns, or a delegation failed. This is the senior's playbook; the per-intern skills (/deepseek /or /gemini /codex /recraft) cover each worker's own usage.
---

# KULI orchestration — the senior's playbook

You (Claude) are the senior. The interns are cheap/specialized workers. You
scope, pick the right worker, **review every result**, and you alone decide
fallback — there is no auto-router, so you always know who actually ran.

## Pick the right intern

| Task | Intern |
|------|--------|
| Cheap text / bulk / summarize / extract | `ask-deepseek` |
| A specific non-DeepSeek model, or compare models | `ask-or -m <slug>` |
| Look at an image/video/screenshot (vision) | `ask-gemini -f` |
| Read a repo, review code, agentic edits | `ask-codex` (`--apply` to edit) |
| Generate an SVG icon/logo/illustration | `ask-recraft` |

Routing rules:
- **New model on an existing backend → just `-m` (use `ask-or`).** New
  capability/backend → a new intern.
- **Cost ladder:** prefer the cheapest worker that clears the bar. deepseek/or
  cheap; gemini/codex mid; recraft ~$0.08/image. Don't send trivial inline-able
  work to an intern — the brief+review overhead can cost more than doing it
  yourself.
- **Parallelism by rate-limit character:** gemini tolerates wide fan-out
  (`-j 8`); codex is the easiest to rate-limit — keep it serial / `-j 2`, give
  it one heavy task done right rather than many parallel ones.

## Health check before delegating

Each `ask-*` records its outcome to a health file. Before a non-trivial
delegation, or after any failure, run `kuli health`. If a worker shows
`rate_limited` (with minutes left) or `auth_failed`, **don't call it** — fall
back. Rate limits self-heal once the window passes; auth does not.

## Fallback ladder (you drive it, transparently)

When the intended intern is unavailable or fails, step DOWN this ladder — never
silently; always tell the user which worker actually ran:

1. **Same family, cheaper** — e.g. drop a model tier (`ask-or` to a cheaper
   slug). (Note: a *rate limit* is per-account, so a cheaper model on the SAME
   benched intern won't help — skip to the next intern.)
2. **Another intern that can do it** — codex ↔ gemini for coding; deepseek/or
   for text.
3. **You (Claude) — last rung only.** Falling back to yourself undoes KULI's
   whole point (you pay twice). So:
   - **Light task** (one question, small fix) → just do it inline, then tell the
     user which intern was exhausted.
   - **Heavy task** (refactor, many files, big generation) → **stop and ask**:
     "all relevant interns are down (codex rate-limited ~30 min, gemini logged
     out) — wait for reset, or want me to do it myself (burns Opus tokens)?"

## Failure handling

- **Rate-limit** → benched until reset; fall back now, retry later automatically.
- **Auth fail** (`401`, `token_invalidated`, "please login") → benched until
  re-login. Tell the user to run the intern's login (`gemini login`,
  `codex login`, or set the key), then `kuli health reset <intern>`.
- **Generic/other error** (bad prompt, network blip) → fix the cause; don't blind
  retry on another intern (if the prompt is wrong it fails everywhere, wasting
  quota). One intern benches only after repeated generic failures.

## Admin

```bash
kuli health                 # show benched interns + minutes left
kuli health reset gemini    # after re-login, before a natural success heals it
kuli health reset           # clear all
```

Related: [[reference-deepseek-delegation]] and the per-intern skills.
