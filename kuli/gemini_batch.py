"""kuli.gemini_batch — fan out many Gemini analysis calls in parallel.

Two modes, picked by input:
  1. media fan-out (positional files): same --prompt applied to each file.
  2. prompt fan-out (stdin): many questions over one shared --context media.
Each call goes through ask-gemini, so every worker stays lean.
"""
import argparse
import shutil

from . import core

PROG = "ask-gemini-batch"
die = core.make_die(PROG)


def cli_path():
    path = shutil.which("ask-gemini")
    if not path:
        die("ask-gemini not found on PATH", 1)
    return path


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Fan out Gemini analysis in parallel.")
    p.add_argument("files", nargs="*", help="media files to fan out over (mode 1)")
    p.add_argument("--prompt", "-p", help="shared question applied to each file (mode 1)")
    p.add_argument("--context", "-c", help="shared media file for stdin prompts (mode 2)")
    p.add_argument("--delimiter", "-d", help="split stdin prompts on this line (else one per line)")
    p.add_argument("--jobs", "-j", type=int, default=4, help="parallel workers (default 4)")
    p.add_argument("--model", "-m", help="explicit model for all calls")
    p.add_argument("--flash", action="store_true", help="use the fast/cheap model for all")
    p.add_argument("--pro", action="store_true", help="use the most capable model for all")
    p.add_argument("--timeout", type=int, help="per-call timeout seconds (env GEMINI_TIMEOUT)")
    p.add_argument("--json", action="store_true", help="emit JSON array of results")
    return p.parse_args()


def shared_flags(args, timeout):
    flags = ["-q", "--timeout", str(timeout)]
    if args.model:
        flags += ["-m", args.model]
    elif args.flash:
        flags.append("--flash")
    elif args.pro:
        flags.append("--pro")
    return flags


def build_jobs(args):
    """Mode 1 = positional files + shared --prompt; mode 2 = stdin prompts."""
    if args.files:
        if not args.prompt:
            die("mode 1 needs --prompt to apply to each file", 1)
        return [(f, ["-f", f, args.prompt]) for f in args.files]
    prompts = core.read_prompts(PROG, args.delimiter)
    ctx = ["-f", args.context] if args.context else []
    return [(p[:60].replace("\n", " "), [*ctx, p]) for p in prompts]


def main():
    args = parse_args()
    timeout = args.timeout if args.timeout is not None else 600
    cli, flags = cli_path(), shared_flags(args, timeout)
    jobs = build_jobs(args)
    results = core.run_batch(jobs, lambda ca: [cli, *flags, *ca], args.jobs, timeout + 30)
    core.emit_batch(results, args.json)
    core.batch_exit(results)


if __name__ == "__main__":
    main()
