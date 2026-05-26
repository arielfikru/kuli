"""kuli.deepseek — text/bulk intern. Calls DeepSeek V4 via OpenRouter.

Backend: OpenRouter chat-completions HTTP API. Stdlib only.
Env: OPENROUTER_API_KEY (required), DEEPSEEK_MODEL / DEEPSEEK_MAX_TOKENS /
DEEPSEEK_TIMEOUT / DEEPSEEK_AUTO_THRESHOLD (optional).
Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import os
import sys

from . import agentic, core, health, openrouter

PROG = "ask-deepseek"
INTERN = "deepseek"
AGENTIC_MODEL = "deepseek/deepseek-v4-pro"  # pro: better tool-use for the codex harness
MODEL_PRO = "deepseek/deepseek-v4-pro"
MODEL_FLASH = "deepseek/deepseek-v4-flash"

die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Call DeepSeek V4 via OpenRouter.")
    p.add_argument("prompt", nargs="*", help="prompt text (else read stdin)")
    p.add_argument("--file", "-f", help="prepend file contents to prompt")
    p.add_argument("--system", "-s", help="system prompt")
    p.add_argument("--model", "-m", help="explicit OpenRouter model slug")
    p.add_argument("--flash", action="store_true", help="use cheaper v4-flash")
    p.add_argument("--auto", action="store_true",
                   help="auto-pick flash (small input) vs pro (large), by token estimate")
    p.add_argument("--temperature", "-t", type=float, default=None)
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="self-consistency: sample N, majority-vote the answer, flag disagreement")
    p.add_argument("--max-tokens", type=int,
                   default=int(os.environ.get("DEEPSEEK_MAX_TOKENS", "262144")),
                   help="max OUTPUT tokens (env DEEPSEEK_MAX_TOKENS)")
    p.add_argument("--reasoning", "-r", nargs="?", const="high", choices=["high", "xhigh"],
                   help="enable thinking mode (effort high|xhigh; bare = high)")
    p.add_argument("--json", action="store_true", help="request JSON object output")
    p.add_argument("--show-thinking", action="store_true",
                   help="also print the reasoning process, not just the final answer")
    p.add_argument("--timeout", type=int,
                   default=int(os.environ.get("DEEPSEEK_TIMEOUT", "600")),
                   help="HTTP timeout seconds (env DEEPSEEK_TIMEOUT)")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress usage stats on stderr")
    p.add_argument("--agentic", action="store_true",
                   help="agentic coding mode: drive DeepSeek through the Codex harness "
                        "(reads/edits a repo). Pairs with --apply / --cd.")
    p.add_argument("--apply", action="store_true", help="(agentic) allow file edits")
    p.add_argument("--cd", "-C", help="(agentic) working root")
    return p.parse_args()


def auto_model(text, system):
    threshold = int(os.environ.get("DEEPSEEK_AUTO_THRESHOLD", "1500"))
    est_tokens = (len(text) + len(system or "")) // 4
    return MODEL_PRO if est_tokens > threshold else MODEL_FLASH


def resolve_model(args, text=""):
    if args.model:
        return args.model
    if args.flash:
        return MODEL_FLASH
    if args.auto:
        return auto_model(text, args.system)
    if os.environ.get("DEEPSEEK_MODEL"):
        return os.environ["DEEPSEEK_MODEL"]
    return MODEL_PRO


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
    user = build_prompt(args)
    if args.agentic:
        sys.exit(agentic.run(AGENTIC_MODEL, user, args.apply, args.cd, args.timeout, PROG))
    model = resolve_model(args, user)
    if args.temperature is None:
        args.temperature = 0.8 if args.consistency else 0.7
    messages = openrouter.build_messages(args.system, user)
    payload = openrouter.build_payload(model, messages, args.temperature,
                                       args.max_tokens, args.json, args.reasoning)

    def sample():
        final, _thinking, usage = openrouter.extract(
            openrouter.call_api(payload, key, args.timeout, die, "kuli-ask-deepseek", INTERN), die)
        return final, usage

    n = args.consistency
    if n and n > 1:
        content, votes, usages = core.run_consistency(sample, n)
        usage = openrouter.sum_usage(usages)
    else:
        content, thinking, usage = openrouter.extract(
            openrouter.call_api(payload, key, args.timeout, die, "kuli-ask-deepseek", INTERN), die)
        votes = None
        if args.show_thinking and thinking:
            print(f"<thinking>\n{thinking}\n</thinking>\n")
    health.record_success(INTERN)
    print(content)
    base = openrouter.format_usage(model, usage) if usage else ""
    core.emit_stats(base, votes, n, args.quiet)


if __name__ == "__main__":
    main()
