"""kuli.core — shared machinery for every KULI intern CLI.

The per-intern adapters (deepseek/gemini/codex) differ only in how they call
their backend. Everything else — reading the prompt, voting across samples,
printing the stats line, fanning out a batch — lives here so it is written
once and behaves identically across interns.
"""
import collections
import concurrent.futures
import json
import subprocess
import sys

MAX_VOTE_WORKERS = 8


def make_die(prog):
    """Return a ``die(msg, code)`` that prefixes errors with the tool name."""
    def die(msg, code):
        print(f"{prog}: {msg}", file=sys.stderr)
        sys.exit(code)
    return die


def read_stdin():
    """Piped stdin as stripped text, or '' when attached to a TTY."""
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


# --- self-consistency voting -------------------------------------------------

def vote_key(text):
    """Answer proxy for voting: normalized last non-empty line, alphanumeric."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    last = lines[-1] if lines else text
    return "".join(ch.lower() for ch in last if ch.isalnum())[:120]


def run_consistency(call_one, n):
    """Sample ``call_one()`` n times in parallel and majority-vote the answer.

    ``call_one`` takes no args and returns ``(text, meta)`` where ``meta`` is
    opaque (usage dict, raw json, …). Returns ``(rep_text, votes, metas)``:
    the winning sample's text, its vote count, and every sample's meta so the
    caller can sum usage or keep the first.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(n, MAX_VOTE_WORKERS)) as pool:
        results = list(pool.map(lambda _: call_one(), range(n)))
    texts = [t for t, _ in results]
    keys = [vote_key(t) for t in texts]
    win_key, votes = collections.Counter(keys).most_common(1)[0]
    rep = next(t for t, k in zip(texts, keys) if k == win_key)
    return rep, votes, [m for _, m in results]


def agreement_suffix(votes, n):
    """`agreement V/N` with a LOW-confidence warning when <= half agree."""
    return f"agreement {votes}/{n}" + ("  ⚠ LOW — verify" if votes * 2 <= n else "")


def emit_stats(base_line, votes, n, quiet):
    """Print the trailing stderr stats line (usage + optional vote agreement)."""
    if quiet:
        return
    line = base_line or ""
    if votes is not None:
        agree = agreement_suffix(votes, n)
        line = f"{line} | {agree}" if line else f"[{agree}]"
    if line:
        print(line, file=sys.stderr)


# --- batch fan-out -----------------------------------------------------------

def read_prompts(prog, delimiter):
    """Read stdin prompts: one per line, or split on a --delimiter line."""
    raw = sys.stdin.read()
    chunks = raw.split(delimiter) if delimiter else raw.splitlines()
    prompts = [c.strip() for c in chunks if c.strip()]
    if not prompts:
        print(f"{prog}: no prompts on stdin", file=sys.stderr)
        sys.exit(1)
    return prompts


def run_batch(jobs, build_argv, workers, timeout=None):
    """Run ``jobs`` (list of ``(label, call_args)``) in parallel via subprocess.

    ``build_argv(call_args)`` returns the full argv for one job. Results keep
    input order: ``[{index, label, output, ok}]``.
    """
    results = [None] * len(jobs)

    def one(index, label, call_args):
        try:
            proc = subprocess.run(build_argv(call_args), capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"index": index, "label": label, "output": "ERROR: timeout", "ok": False}
        if proc.returncode != 0:
            return {"index": index, "label": label,
                    "output": f"ERROR: {proc.stderr.strip()}", "ok": False}
        return {"index": index, "label": label, "output": proc.stdout.rstrip("\n"), "ok": True}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one, i, lbl, ca) for i, (lbl, ca) in enumerate(jobs)]
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results[r["index"]] = r
    return results


def emit_batch(results, as_json):
    """Print batch results as a JSON array or human-readable blocks."""
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    for r in results:
        print(f"=== [{r['index']}] {r['label']} ===")
        print(r["output"])
        print()


def batch_exit(results):
    """Exit 2 if any job failed (call after emitting)."""
    if any(not r["ok"] for r in results):
        sys.exit(2)
