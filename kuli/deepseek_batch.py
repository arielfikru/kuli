"""kuli.deepseek_batch — fan out many prompts to ask-deepseek in parallel.

A shared --system/--context prefix is cached after the first call (~0.25x for
cached tokens on OpenRouter). Prompts: one per line, or split on --delimiter.
"""
import argparse
import shutil

from . import core

PROG = "ask-deepseek-batch"
die = core.make_die(PROG)


def cli_path():
    path = shutil.which("ask-deepseek")
    if not path:
        die("ask-deepseek not found on PATH", 1)
    return path


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Fan out prompts to DeepSeek in parallel.")
    p.add_argument("--system", "-s", help="shared system prompt (cached prefix)")
    p.add_argument("--context", "-c", help="shared context file (cached prefix)")
    p.add_argument("--delimiter", "-d", help="split prompts on this line (else one per line)")
    p.add_argument("--jobs", "-j", type=int, default=4, help="parallel workers (default 4)")
    p.add_argument("--flash", action="store_true", help="use v4-flash for all")
    p.add_argument("--auto", action="store_true", help="auto-route each by size")
    p.add_argument("--reasoning", "-r", nargs="?", const="high", choices=["high", "xhigh"],
                   help="enable thinking mode for all (high|xhigh)")
    p.add_argument("--model", "-m", help="explicit model slug for all")
    p.add_argument("--temperature", "-t", type=float)
    p.add_argument("--max-tokens", type=int)
    p.add_argument("--json", action="store_true", help="emit JSON array of results")
    return p.parse_args()


def shared_flags(args):
    flags = ["-q"]
    if args.system:
        flags += ["-s", args.system]
    if args.context:
        flags += ["-f", args.context]
    if args.flash:
        flags.append("--flash")
    if args.auto:
        flags.append("--auto")
    if args.reasoning:
        flags += ["-r", args.reasoning]
    if args.model:
        flags += ["-m", args.model]
    if args.temperature is not None:
        flags += ["-t", str(args.temperature)]
    if args.max_tokens is not None:
        flags += ["--max-tokens", str(args.max_tokens)]
    return flags


def main():
    args = parse_args()
    cli, flags = cli_path(), shared_flags(args)
    prompts = core.read_prompts(PROG, args.delimiter)
    jobs = [(p[:60].replace("\n", " "), [p]) for p in prompts]
    results = core.run_batch(jobs, lambda ca: [cli, *flags, *ca], args.jobs)
    core.emit_batch(results, args.json)
    core.batch_exit(results)


if __name__ == "__main__":
    main()
