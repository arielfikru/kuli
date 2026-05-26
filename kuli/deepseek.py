"""kuli.deepseek — text/bulk intern. Calls DeepSeek V4 via OpenRouter.

Backend: OpenRouter chat-completions HTTP API. Stdlib only.
Env: OPENROUTER_API_KEY (required), DEEPSEEK_MODEL / DEEPSEEK_MAX_TOKENS /
DEEPSEEK_TIMEOUT / DEEPSEEK_AUTO_THRESHOLD (optional).
Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from . import core

PROG = "ask-deepseek"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
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


def build_payload(args, model, user):
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": user})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "usage": {"include": True},
    }
    if args.json:
        payload["response_format"] = {"type": "json_object"}
    if args.reasoning:
        payload["reasoning"] = {"effort": args.reasoning}
    return payload


def call_api(payload, key, timeout):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claude-code.local/kuli",
            "X-Title": "kuli-ask-deepseek",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", 2)
    except TimeoutError:
        die(f"timed out after {timeout}s — raise --timeout or lower --reasoning effort", 2)
    except urllib.error.URLError as e:
        die(f"network error: {e.reason}", 2)


def extract(data):
    """Return (final_answer, thinking, usage)."""
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError):
        die(f"unexpected response: {json.dumps(data)[:500]}", 2)
    thinking = msg.get("reasoning") or msg.get("reasoning_content") or ""
    final = msg.get("content") or thinking
    if not final:
        die(f"empty content: {json.dumps(data)[:500]}", 2)
    return final, thinking, data.get("usage", {})


def format_usage(model, usage):
    pt = usage.get("prompt_tokens", "?")
    ct = usage.get("completion_tokens", "?")
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    line = f"[{model} | in {pt} out {ct} tok"
    if cached:
        line += f" | cached {cached} (~0.25x)"
    if usage.get("cache_discount") is not None:
        line += f" | discount ${usage['cache_discount']:.6f}"
    return line + "]"


def sum_usage(usages):
    total = {"prompt_tokens": 0, "completion_tokens": 0}
    for u in usages:
        total["prompt_tokens"] += u.get("prompt_tokens", 0)
        total["completion_tokens"] += u.get("completion_tokens", 0)
    return total


def main():
    args = parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        die("OPENROUTER_API_KEY not set", 1)
    user = build_prompt(args)
    model = resolve_model(args, user)
    if args.temperature is None:
        args.temperature = 0.8 if args.consistency else 0.7
    payload = build_payload(args, model, user)

    def sample():
        final, _thinking, usage = extract(call_api(payload, key, args.timeout))
        return final, usage

    n = args.consistency
    if n and n > 1:
        content, votes, usages = core.run_consistency(sample, n)
        usage = sum_usage(usages)
    else:
        content, thinking, usage = extract(call_api(payload, key, args.timeout))
        votes = None
        if args.show_thinking and thinking:
            print(f"<thinking>\n{thinking}\n</thinking>\n")
    print(content)
    base = format_usage(model, usage) if usage else ""
    core.emit_stats(base, votes, n, args.quiet)


if __name__ == "__main__":
    main()
