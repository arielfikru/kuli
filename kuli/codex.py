"""kuli.codex — agentic coding intern. Wraps OpenAI's `codex exec`.

Two modes:
  - read-only (default): codex inspects the repo and answers in text. Safe;
    no file writes. Use for code review, "how does X work", second opinions.
  - --apply: codex may EDIT FILES and run commands (sandbox=workspace-write).
    Mutating. Run it inside a throwaway git worktree and review the diff before
    keeping anything — never merge codex's work blind.

Danger sandbox modes (`danger-full-access`, approval/sandbox bypass) are
deliberately NOT exposed by this wrapper. Stdlib only.
Env: CODEX_MODEL / CODEX_TIMEOUT (optional). Auth via `codex login` or
OPENAI_API_KEY (handled by the codex CLI itself).
Exit codes: 0 ok, 1 usage/input error, 2 codex error.
"""
import argparse
import os
import subprocess
import sys
import tempfile

from . import core, health

PROG = "ask-codex"
INTERN = "codex"
DEFAULT_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "600"))

die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Delegate to OpenAI Codex (codex exec).")
    p.add_argument("prompt", nargs="*", help="task/question (else read stdin)")
    p.add_argument("--file", "-f", help="prepend file contents to the prompt")
    p.add_argument("--image", "-i", action="append", default=[],
                   help="image to attach to the prompt; repeatable")
    p.add_argument("--apply", action="store_true",
                   help="AGENTIC: allow file edits (sandbox=workspace-write). "
                        "Default is read-only. Run in a throwaway worktree + review the diff.")
    p.add_argument("--cd", "-C", help="working root for codex (default: cwd)")
    p.add_argument("--model", "-m", help="explicit codex model")
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="read-only only: sample N, majority-vote the answer")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"seconds before giving up (default {DEFAULT_TIMEOUT}, env CODEX_TIMEOUT)")
    p.add_argument("--json", action="store_true", help="stream raw codex JSONL events to stdout")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress stats on stderr")
    return p.parse_args()


def build_prompt(args):
    parts = []
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                parts.append(fh.read())
        except OSError as e:
            die(f"cannot read --file: {e}", 1)
    if args.prompt:
        parts.append(" ".join(args.prompt))
    else:
        piped = core.read_stdin()
        if piped:
            parts.append(piped)
    text = "\n\n".join(p for p in parts if p.strip())
    if not text.strip():
        die("empty prompt (pass args, --file, or pipe stdin)", 1)
    return text


def build_cmd(args, prompt, last_msg_file):
    sandbox = "workspace-write" if args.apply else "read-only"
    cmd = ["codex", "exec", "--sandbox", sandbox, "--color", "never"]
    if not args.apply:
        # Pure Q&A: don't litter session files and allow use outside a repo.
        cmd += ["--ephemeral", "--skip-git-repo-check"]
    if args.cd:
        cmd += ["--cd", args.cd]
    model = args.model or os.environ.get("CODEX_MODEL")
    if model:
        cmd += ["-m", model]
    for img in args.image:
        cmd += ["-i", img]
    if args.json:
        cmd.append("--json")
    elif last_msg_file:
        cmd += ["-o", last_msg_file]
    cmd.append(prompt)
    return cmd


def run_codex(args, prompt):
    """Run codex once. Returns the agent's final message text."""
    last_file = None
    if not args.json:
        fd, last_file = tempfile.mkstemp(prefix="ask-codex-", suffix=".txt")
        os.close(fd)
    try:
        cmd = build_cmd(args, prompt, last_file)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, timeout=args.timeout)
        except FileNotFoundError:
            die("codex CLI not found on PATH", 2)
        except subprocess.TimeoutExpired:
            health.record_failure(INTERN, "timed out", 2)
            die(f"codex timed out after {args.timeout}s — raise --timeout", 2)
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout)[:500]
            health.record_failure(INTERN, msg, 2)
            die(f"codex exited {proc.returncode}: {msg}", 2)
        if args.json:
            return proc.stdout
        with open(last_file, encoding="utf-8") as fh:
            return fh.read().strip() or proc.stdout.strip()
    finally:
        if last_file:
            try:
                os.unlink(last_file)
            except OSError:
                pass


def main():
    args = parse_args()
    if args.apply and args.consistency:
        die("--consistency cannot combine with --apply (would run N mutations)", 1)
    prompt = build_prompt(args)

    n = args.consistency
    if n and n > 1:
        text, votes, _ = core.run_consistency(lambda: (run_codex(args, prompt), None), n)
    else:
        text, votes = run_codex(args, prompt), None
    health.record_success(INTERN)
    print(text)
    if args.apply and not args.quiet:
        print(f"{PROG}: ⚠ codex ran in WRITE mode — review the diff before keeping changes",
              file=sys.stderr)
    base = f"[codex {'apply' if args.apply else 'read-only'}]"
    core.emit_stats(base, votes, n, args.quiet)


if __name__ == "__main__":
    main()
