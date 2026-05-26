"""kuli.codex_batch — fan out many read-only codex questions in parallel.

Read-only only by design: batching file-mutating --apply runs would race on
the same tree. For agentic work run a single ask-codex --apply in a worktree.
Prompts: one per line, or split on --delimiter. Shared --cd/--model apply to all.
"""
import argparse
import shutil

from . import core

PROG = "ask-codex-batch"
die = core.make_die(PROG)


def cli_path():
    path = shutil.which("ask-codex")
    if not path:
        die("ask-codex not found on PATH", 1)
    return path


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Fan out read-only codex questions.")
    p.add_argument("--cd", "-C", help="shared working root for all calls")
    p.add_argument("--delimiter", "-d", help="split prompts on this line (else one per line)")
    p.add_argument("--jobs", "-j", type=int, default=4, help="parallel workers (default 4)")
    p.add_argument("--model", "-m", help="explicit model for all")
    p.add_argument("--timeout", type=int, help="per-call timeout seconds (env CODEX_TIMEOUT)")
    p.add_argument("--json", action="store_true", help="emit JSON array of results")
    return p.parse_args()


def shared_flags(args, timeout):
    flags = ["-q", "--timeout", str(timeout)]
    if args.cd:
        flags += ["-C", args.cd]
    if args.model:
        flags += ["-m", args.model]
    return flags


def main():
    args = parse_args()
    timeout = args.timeout if args.timeout is not None else 600
    cli, flags = cli_path(), shared_flags(args, timeout)
    prompts = core.read_prompts(PROG, args.delimiter)
    jobs = [(p[:60].replace("\n", " "), [p]) for p in prompts]
    results = core.run_batch(jobs, lambda ca: [cli, *flags, *ca], args.jobs, timeout + 30)
    core.emit_batch(results, args.json)
    core.batch_exit(results)


if __name__ == "__main__":
    main()
