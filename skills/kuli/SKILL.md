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
| Heavy / long-horizon / precise coding | `ask-codex` (`--apply` to edit) |
| High-volume / parallel / visual coding, or 2nd-opinion review | `ask-gemini-code` (`--apply`, `-w`) |
| Read a repo, review code | `ask-codex` or `ask-gemini-code` (read-only) |
| Generate an SVG icon/logo/illustration | `ask-recraft` |

Routing rules:
- **New model on an existing backend → just `-m` (use `ask-or`).** New
  capability/backend → a new intern.
- **Cheap agentic coding (no ChatGPT quota):** the Codex harness can run any
  OpenRouter model — `ask-deepseek --agentic` / `ask-or -m <slug> --agentic` /
  `ask-codex --or-model <slug>`. Use when codex (GPT-5.5) is rate-limited/logged
  out but you still need repo read/edit. Token-heavy; pick a capable slug for
  `--apply`.
- **Cost ladder:** prefer the cheapest worker that clears the bar. deepseek/or
  cheap; gemini/codex mid; recraft ~$0.08/image. Don't send trivial inline-able
  work to an intern — the brief+review overhead can cost more than doing it
  yourself.
- **Parallelism by rate-limit character:** gemini tolerates wide fan-out
  (`-j 8`); codex is the easiest to rate-limit — keep it serial / `-j 2`, give
  it one heavy task done right rather than many parallel ones.

## Coding: pick the lane

Repo coding always goes **agentic** — the lane reads the repo itself, so you hand
only the task + `-C dir`, never file contents (keeps big context off Opus).
Default to the cheapest lane that clears the bar:

1. **`ask-deepseek --agentic` — the default coding delegate.** Simple→medium repo
   read/edit, cheapest agentic (Codex harness on OpenRouter). `--apply` to edit
   (isolate in a worktree); read-only otherwise.
2. **`ask-gemini-code`** — step up for high-volume / parallel / many-file work, a
   cross-family diff review, or when the task needs vision. Wide fan-out (`-j 8`).
3. **`ask-codex`** — heaviest precision / long-horizon; one task done right.
   Serial (`-j 2`, easiest to rate-limit).

deepseek **text** mode is NOT a coding lane — it is blind. Reach for it only for
non-repo text: explain/summarize pasted code, draft boilerplate or tests from a
`-f` file, bulk text transforms. Trivial inline edits: just do them yourself —
the brief+review overhead outweighs them.

### When YOU (Claude) code, not an intern

Delegation is for **bounded, well-specified** work. Keep these on yourself — you
are the senior, not a last resort:

- **New feature / new concept** — net-new design where the shape is not yet
  settled.
- **Super-heavy or architectural** — decisions that ripple across the codebase,
  or judgment calls an intern would guess at.
- **Underspecified** — if you cannot write a tight brief, you cannot delegate it;
  do it yourself (or split off the bounded sub-parts to interns).

Rule of thumb: can you hand it off as a crisp, self-contained task? → intern.
Does it need design judgment, novel structure, or whole-system context? → you.
You may still use an intern for a *bounded slice* (scaffold, tests, a mechanical
refactor) while you own the design.

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
