"""kuli.ask_or — generic OpenRouter intern. Any model, your choice.

Same OpenRouter plumbing as the deepseek preset, but model-agnostic: you pick
the slug (anthropic/claude-…, openai/gpt-…, google/gemini-…, x-ai/grok-…,
qwen/…, meta-llama/…, etc). Model is REQUIRED — via -m or the OPENROUTER_MODEL
env var; there is deliberately no silent default so you never spend on a model
you didn't choose. Stdlib only.
Env: OPENROUTER_API_KEY (required), OPENROUTER_MODEL (default model slug),
OPENROUTER_MAX_TOKENS / OPENROUTER_TIMEOUT (optional).
Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import os

import sys

from . import agentic, core, health, openrouter

PROG = "ask-or"
INTERN = "or"
die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG,
                                description="Call any OpenRouter model. Pick the model with -m.")
    p.add_argument("prompt", nargs="*", help="prompt text (else read stdin)")
    p.add_argument("--model", "-m", help="OpenRouter model slug (or env OPENROUTER_MODEL)")
    p.add_argument("--file", "-f", help="prepend file contents to prompt")
    p.add_argument("--system", "-s", help="system prompt")
    p.add_argument("--temperature", "-t", type=float, default=None)
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="self-consistency: sample N, majority-vote, flag disagreement")
    p.add_argument("--max-tokens", type=int,
                   default=int(os.environ.get("OPENROUTER_MAX_TOKENS", "262144")),
                   help="max OUTPUT tokens (env OPENROUTER_MAX_TOKENS)")
    p.add_argument("--reasoning", "-r", nargs="?", const="high", choices=["high", "xhigh"],
                   help="enable thinking mode if the model supports it (high|xhigh)")
    p.add_argument("--json", action="store_true", help="request JSON object output")
    p.add_argument("--show-thinking", action="store_true",
                   help="also print the reasoning process, not just the final answer")
    p.add_argument("--timeout", type=int,
                   default=int(os.environ.get("OPENROUTER_TIMEOUT", "600")),
                   help="HTTP timeout seconds (env OPENROUTER_TIMEOUT)")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress usage stats on stderr")
    p.add_argument("--agentic", action="store_true",
                   help="agentic coding mode: drive this model through the Codex harness "
                        "(reads/edits a repo). Pairs with --apply / --cd.")
    p.add_argument("--apply", action="store_true", help="(agentic) allow file edits")
    p.add_argument("--cd", "-C", help="(agentic) working root")
    return p.parse_args()


def resolve_model(args):
    model = args.model or os.environ.get("OPENROUTER_MODEL")
    if not model:
        die("no model — pass -m <slug> or set OPENROUTER_MODEL "
            "(e.g. openai/gpt-5, anthropic/claude-opus-4, google/gemini-3-pro)", 1)
    return model


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


def main():
    args = parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        die("OPENROUTER_API_KEY not set", 1)
    model = resolve_model(args)
    user = build_prompt(args)
    if args.agentic:
        sys.exit(agentic.run(model, user, args.apply, args.cd, args.timeout, PROG))
    if args.temperature is None:
        args.temperature = 0.8 if args.consistency else 0.7
    messages = openrouter.build_messages(args.system, user)
    payload = openrouter.build_payload(model, messages, args.temperature,
                                       args.max_tokens, args.json, args.reasoning)

    def sample():
        final, _thinking, usage = openrouter.extract(
            openrouter.call_api(payload, key, args.timeout, die, "kuli-ask-or", INTERN), die)
        return final, usage

    n = args.consistency
    if n and n > 1:
        content, votes, usages = core.run_consistency(sample, n)
        usage = openrouter.sum_usage(usages)
    else:
        content, thinking, usage = openrouter.extract(
            openrouter.call_api(payload, key, args.timeout, die, "kuli-ask-or", INTERN), die)
        votes = None
        if args.show_thinking and thinking:
            print(f"<thinking>\n{thinking}\n</thinking>\n")
    health.record_success(INTERN)
    print(content)
    base = openrouter.format_usage(model, usage) if usage else ""
    core.emit_stats(base, votes, n, args.quiet)


if __name__ == "__main__":
    main()
