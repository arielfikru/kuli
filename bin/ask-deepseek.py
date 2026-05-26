#!/usr/bin/env python3
"""ask-deepseek — call DeepSeek V4 via OpenRouter. Stdlib only.

Usage:
  ask-deepseek "prompt text"
  echo "prompt" | ask-deepseek
  ask-deepseek --file notes.md "summarize this"
  ask-deepseek --flash "cheap quick task"
  ask-deepseek --system "You are a researcher" "question"

Env:
  OPENROUTER_API_KEY   required
  DEEPSEEK_MODEL       optional, overrides default model

Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_PRO = "deepseek/deepseek-v4-pro"
MODEL_FLASH = "deepseek/deepseek-v4-flash"


def die(msg, code):
    print(f"ask-deepseek: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args():
    p = argparse.ArgumentParser(add_help=True, description="Call DeepSeek V4 via OpenRouter.")
    p.add_argument("prompt", nargs="*", help="prompt text (else read stdin)")
    p.add_argument("--file", "-f", help="prepend file contents to prompt")
    p.add_argument("--system", "-s", help="system prompt")
    p.add_argument("--model", "-m", help="explicit OpenRouter model slug")
    p.add_argument("--flash", action="store_true", help="use cheaper v4-flash")
    p.add_argument("--temperature", "-t", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--json", action="store_true", help="request JSON object output")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress usage stats on stderr")
    return p.parse_args()


def resolve_model(args):
    if args.model:
        return args.model
    if os.environ.get("DEEPSEEK_MODEL"):
        return os.environ["DEEPSEEK_MODEL"]
    return MODEL_FLASH if args.flash else MODEL_PRO


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
    elif not sys.stdin.isatty():
        parts.append(sys.stdin.read())
    text = "\n\n".join(p for p in parts if p.strip())
    if not text.strip():
        die("empty prompt (pass args, --file, or pipe stdin)", 1)
    return text


def build_messages(system, user):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs


def build_payload(args, model, messages):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "usage": {"include": True},
    }
    if args.json:
        payload["response_format"] = {"type": "json_object"}
    return payload


def call_api(payload, key):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claude-code.local/ask-deepseek",
            "X-Title": "ask-deepseek",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", 2)
    except urllib.error.URLError as e:
        die(f"network error: {e.reason}", 2)


def extract(data):
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        die(f"unexpected response: {json.dumps(data)[:500]}", 2)
    return content, data.get("usage", {})


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


def main():
    args = parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        die("OPENROUTER_API_KEY not set", 1)
    model = resolve_model(args)
    user = build_prompt(args)
    payload = build_payload(args, model, build_messages(args.system, user))
    content, usage = extract(call_api(payload, key))
    print(content)
    if not args.quiet and usage:
        print(format_usage(model, usage), file=sys.stderr)


if __name__ == "__main__":
    main()
