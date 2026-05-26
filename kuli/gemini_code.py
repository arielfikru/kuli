"""kuli.gemini_code — gemini as a coding intern (reads/edits the real repo).

Unlike ask-gemini (vision; runs in an empty temp dir so it can't see the repo),
this runs gemini IN your working directory so it can read project files. Two
modes:
  - read-only (default): `--approval-mode plan` — inspects + answers, no writes.
  - --apply: `--approval-mode auto_edit` — may EDIT files. Prefer --worktree
    (gemini's built-in `-w`, a throwaway git worktree) and review the diff;
    never merge blind. Shell-command auto-exec (yolo) is deliberately not
    exposed — auto_edit approves edits only.

Shares health with the vision intern (same `gemini` account/quota).
Env: GEMINI_MODEL / GEMINI_TIMEOUT. Exit: 0 ok, 1 input, 2 gemini error.
"""
import argparse
import json
import os
import subprocess
import sys

from . import core, health
from .gemini import format_usage

PROG = "ask-gemini-code"
INTERN = "gemini"
DEFAULT_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "600"))
die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Gemini coding (reads/edits the repo).")
    p.add_argument("prompt", nargs="*", help="task/question (else read stdin)")
    p.add_argument("--apply", action="store_true",
                   help="AGENTIC: allow file edits (auto_edit). Default is read-only (plan). "
                        "Prefer --worktree + review the diff.")
    p.add_argument("--worktree", "-w", action="store_true",
                   help="run in a fresh git worktree (recommended with --apply)")
    p.add_argument("--cd", "-C", help="working root for gemini (default: cwd)")
    p.add_argument("--model", "-m", help="explicit Gemini model name")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"seconds before giving up (default {DEFAULT_TIMEOUT}, env GEMINI_TIMEOUT)")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress stats on stderr")
    return p.parse_args()


def build_prompt(args):
    parts = []
    if args.prompt:
        parts.append(" ".join(args.prompt))
    piped = core.read_stdin()
    if piped:
        parts.append(piped)
    text = " ".join(parts).strip()
    if not text:
        die("empty prompt (pass args or pipe stdin)", 1)
    return text


def build_cmd(args, prompt):
    mode = "auto_edit" if args.apply else "plan"
    cmd = ["gemini", "-p", prompt, "-o", "json", "--approval-mode", mode]
    if args.worktree:
        cmd.append("-w")
    if args.model:
        cmd += ["-m", args.model]
    return cmd


def run_gemini(args, prompt):
    cmd = build_cmd(args, prompt)
    try:
        proc = subprocess.run(cmd, cwd=args.cd or None, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=args.timeout)
    except FileNotFoundError:
        die("gemini CLI not found on PATH", 2)
    except subprocess.TimeoutExpired:
        health.record_failure(INTERN, "timed out", 2)
        die(f"gemini timed out after {args.timeout}s — raise --timeout", 2)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout)[:500]
        health.record_failure(INTERN, msg, 2)
        die(f"gemini exited {proc.returncode}: {msg}", 2)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        die(f"unparseable gemini output: {proc.stdout[:500]}", 2)


def main():
    args = parse_args()
    prompt = build_prompt(args)
    data = run_gemini(args, prompt)
    health.record_success(INTERN)
    print(data.get("response", ""))
    if args.apply and not args.quiet:
        print(f"{PROG}: ⚠ gemini ran in EDIT mode — review the diff before keeping changes",
              file=sys.stderr)
    core.emit_stats(format_usage(data) or "", None, None, args.quiet)


if __name__ == "__main__":
    main()
