#!/usr/bin/env python3
"""make-intern — scaffold a new KULI intern from a template.

Generates the adapter, batch fan-out, bin launcher, and a skill stub for a new
intern, wired to the shared `kuli.core`. You fill in the one backend-specific
function (the TODO) and add the MCP tool + install.sh skill name.

Usage:
  scripts/make-intern.py <name> --shape {api|cli} [--desc "one line"]

  --shape api   backend = an HTTP API you call (like deepseek/or)
  --shape cli   backend = a local CLI you subprocess (like gemini/codex)

Refuses to overwrite existing files. Run from anywhere; paths resolve to the
repo root (this script's parent dir).
"""
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def die(msg):
    print(f"make-intern: {msg}", file=sys.stderr)
    sys.exit(1)


ADAPTER_API = '''"""kuli.__NAME__ — TODO one-line description (API-backed intern).

Backend: TODO which HTTP API. Stdlib only. Env: TODO keys.
Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import os

from . import core

PROG = "ask-__NAME__"
die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="TODO")
    p.add_argument("prompt", nargs="*", help="prompt text (else read stdin)")
    p.add_argument("--file", "-f", help="prepend file contents to prompt")
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="self-consistency: sample N, majority-vote")
    p.add_argument("--timeout", type=int, default=600, help="timeout seconds")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress stats")
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
    text = "\\n\\n".join(p for p in parts if p.strip())
    if not text.strip():
        die("empty prompt (pass args, --file, or pipe stdin)", 1)
    return text


def call_backend(prompt, args):
    """TODO: call the API, return (answer_text, usage_dict). Use `die` on error."""
    raise NotImplementedError("implement call_backend for ask-__NAME__")


def format_usage(usage):
    return f"[ask-__NAME__ | {usage}]" if usage else ""


def main():
    args = parse_args()
    prompt = build_prompt(args)
    n = args.consistency
    if n and n > 1:
        text, votes, metas = core.run_consistency(lambda: call_backend(prompt, args), n)
        usage = metas[0]
    else:
        text, usage = call_backend(prompt, args)
        votes = None
    print(text)
    core.emit_stats(format_usage(usage), votes, n, args.quiet)


if __name__ == "__main__":
    main()
'''

ADAPTER_CLI = '''"""kuli.__NAME__ — TODO one-line description (CLI-backed intern).

Backend: subprocess a local CLI. Stdlib only. Env: TODO.
Exit codes: 0 ok, 1 usage/input error, 2 CLI error.
"""
import argparse
import subprocess

from . import core

PROG = "ask-__NAME__"
die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="TODO")
    p.add_argument("prompt", nargs="*", help="prompt text (else read stdin)")
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="self-consistency: sample N, majority-vote")
    p.add_argument("--timeout", type=int, default=600, help="timeout seconds")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress stats")
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


def call_backend(prompt, args):
    """TODO: build the CLI argv, run it, return (answer_text, meta)."""
    cmd = ["TODO-cli", prompt]  # TODO: real command + flags
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=args.timeout)
    except FileNotFoundError:
        die("TODO-cli not found on PATH", 2)
    except subprocess.TimeoutExpired:
        die(f"timed out after {args.timeout}s", 2)
    if proc.returncode != 0:
        die(f"exited {proc.returncode}: {(proc.stderr or proc.stdout)[:500]}", 2)
    return proc.stdout.strip(), None


def main():
    args = parse_args()
    prompt = build_prompt(args)
    n = args.consistency
    if n and n > 1:
        text, votes, _ = core.run_consistency(lambda: call_backend(prompt, args), n)
    else:
        text, _ = call_backend(prompt, args)
        votes = None
    print(text)
    core.emit_stats("", votes, n, args.quiet)


if __name__ == "__main__":
    main()
'''

ADAPTER_PERSONA = '''"""kuli.__NAME__ — __DESC__

A persona intern: a fixed OpenRouter model + baked-in system prompt, so the job
is set once here instead of per call. Same OpenRouter plumbing as ask-or.
Env: OPENROUTER_API_KEY (required).
Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import os

from . import core, openrouter

PROG = "ask-__NAME__"
MODEL = "__MODEL__"
SYSTEM = "__SYSTEM__"
die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="__DESC__")
    p.add_argument("prompt", nargs="*", help="prompt text (else read stdin)")
    p.add_argument("--file", "-f", help="prepend file contents to prompt")
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="self-consistency: sample N, majority-vote")
    p.add_argument("--temperature", "-t", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=262144, help="max output tokens")
    p.add_argument("--timeout", type=int, default=600, help="HTTP timeout seconds")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress stats")
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
    text = "\\n\\n".join(p for p in parts if p.strip())
    if not text.strip():
        die("empty prompt (pass args, --file, or pipe stdin)", 1)
    return text


def main():
    args = parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        die("OPENROUTER_API_KEY not set", 1)
    user = build_prompt(args)
    if args.temperature is None:
        args.temperature = 0.9  # persona default; creative leans hot
    messages = openrouter.build_messages(SYSTEM, user)
    payload = openrouter.build_payload(MODEL, messages, args.temperature, args.max_tokens)

    def sample():
        final, _t, usage = openrouter.extract(
            openrouter.call_api(payload, key, args.timeout, die, PROG), die)
        return final, usage

    n = args.consistency
    if n and n > 1:
        content, votes, usages = core.run_consistency(sample, n)
        usage = openrouter.sum_usage(usages)
    else:
        content, _t, usage = sample()
        votes = None
    print(content)
    core.emit_stats(openrouter.format_usage(MODEL, usage) if usage else "",
                    votes, n, args.quiet)


if __name__ == "__main__":
    main()
'''

ADAPTER_IMAGE = r'''"""kuli.__NAME__ — __DESC__

An image-generation intern: a fixed OpenRouter image model. Writes the generated
image to a file and prints its path (not text to stdout). Optional single input
image via -i. Env: OPENROUTER_API_KEY.
Exit codes: 0 ok, 1 usage/input error, 2 API error.
"""
import argparse
import base64
import mimetypes
import os
import time

from . import core, openrouter

PROG = "ask-__NAME__"
MODEL = "__MODEL__"
STYLE = "__SYSTEM__"  # optional style preamble prepended to every prompt
die = core.make_die(PROG)

EXT = {"image/svg+xml": "svg", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="__DESC__")
    p.add_argument("prompt", nargs="*", help="text prompt (else read stdin)")
    p.add_argument("--image", "-i", help="optional single input image to guide output")
    p.add_argument("--out", "-o", help="output file path (default: auto-named in cwd)")
    p.add_argument("--timeout", type=int, default=600, help="HTTP timeout seconds")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress stats")
    return p.parse_args()


def build_text(args):
    parts = [STYLE] if STYLE else []
    if args.prompt:
        parts.append(" ".join(args.prompt))
    else:
        piped = core.read_stdin()
        if piped:
            parts.append(piped)
    text = " ".join(p for p in parts if p.strip()).strip()
    if not text:
        die("empty prompt (pass args or pipe stdin)", 1)
    return text


def build_content(text, image):
    if not image:
        return text
    ap = os.path.abspath(image)
    if not os.path.exists(ap):
        die(f"input image not found: {image}", 1)
    mime = mimetypes.guess_type(ap)[0] or "image/png"
    with open(ap, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return [{"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]


def extract_image(data):
    try:
        imgs = data["choices"][0]["message"].get("images") or []
    except (KeyError, IndexError):
        die(f"unexpected response: {data}", 2)
    if not imgs:
        die("no image in response", 2)
    url = imgs[0].get("image_url", {}).get("url", "")
    if not url.startswith("data:"):
        die("response image is not a data URL", 2)
    header, _, b64 = url.partition(",")
    mime = header[5:].split(";")[0]
    return mime, base64.b64decode(b64)


def main():
    args = parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        die("OPENROUTER_API_KEY not set", 1)
    text = build_text(args)
    payload = {"model": MODEL, "modalities": ["image"],
               "messages": [{"role": "user", "content": build_content(text, args.image)}]}
    data = openrouter.call_api(payload, key, args.timeout, die, PROG)
    mime, blob = extract_image(data)
    out = args.out or f"{PROG}-{int(time.time() * 1000)}-{os.getpid()}.{EXT.get(mime, 'bin')}"
    with open(out, "wb") as fh:
        fh.write(blob)
    print(os.path.abspath(out))
    usage = data.get("usage", {})
    core.emit_stats(openrouter.format_usage(MODEL, usage) if usage else "", None, None, args.quiet)


if __name__ == "__main__":
    main()
'''

BATCH = '''"""kuli.__NAME___batch — fan out many prompts to ask-__NAME__ in parallel.

Prompts: one per line, or split on --delimiter.
"""
import argparse
import shutil

from . import core

PROG = "ask-__NAME__-batch"
die = core.make_die(PROG)


def cli_path():
    path = shutil.which("ask-__NAME__")
    if not path:
        die("ask-__NAME__ not found on PATH", 1)
    return path


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Fan out ask-__NAME__ in parallel.")
    p.add_argument("--delimiter", "-d", help="split prompts on this line (else one per line)")
    p.add_argument("--jobs", "-j", type=int, default=4, help="parallel workers (default 4)")
    p.add_argument("--json", action="store_true", help="emit JSON array of results")
    return p.parse_args()


def main():
    args = parse_args()
    cli = cli_path()
    prompts = core.read_prompts(PROG, args.delimiter)
    jobs = [(p[:60].replace("\\n", " "), [p]) for p in prompts]
    results = core.run_batch(jobs, lambda ca: [cli, "-q", *ca], args.jobs)
    core.emit_batch(results, args.json)
    core.batch_exit(results)


if __name__ == "__main__":
    main()
'''

LAUNCHER = '''#!/usr/bin/env python3
"""KULI launcher for ask-__NAME__ — thin entry into kuli.__MOD__:main."""
import os
import sys

_bin = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_bin, "..", "lib"))
from kuli.__MOD__ import main

main()
'''

SKILL = '''---
name: __NAME__
description: __DESC__ Trigger when user says "pakai __NAME__", "/__NAME__". Claude stays orchestrator and validates output.
---

# __NAME__ delegation — TODO persona

Treat ask-__NAME__ as an intern under you (Claude): scope it, hand it the
material, review before shipping.

## Tool

`ask-__NAME__` (at `~/.claude/bin/ask-__NAME__`).

```bash
ask-__NAME__ "TODO example"
printf 'a\\nb\\n' | ask-__NAME__-batch -j 4
```

Flags: `-f FILE` (api shape), `-c N` (self-consistency vote), `--timeout`, `-q`.

## When to delegate
- TODO

## When NOT to
- Final correctness calls → Claude, never blind.

## Notes
- Related: [[reference-deepseek-delegation]] — same senior/intern discipline.
'''


def write(path, text, executable=False):
    if path.exists():
        die(f"refusing to overwrite existing {path.relative_to(REPO)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if executable:
        path.chmod(0o755)
    print(f"  created {path.relative_to(REPO)}")


def main():
    ap = argparse.ArgumentParser(prog="make-intern", description="Scaffold a new KULI intern.")
    ap.add_argument("name", help="intern name (kebab/lowercase, e.g. grok, mistral, ollama)")
    ap.add_argument("--shape", required=True, choices=["api", "cli", "persona", "image"],
                    help="api = HTTP backend; cli = subprocess a local CLI; "
                         "persona = fixed OpenRouter chat model + baked-in system prompt; "
                         "image = fixed OpenRouter image model, writes image files")
    ap.add_argument("--desc", default="TODO one-line description of this intern.",
                    help="skill description (one line)")
    ap.add_argument("--model", help="OpenRouter slug (required for --shape persona)")
    ap.add_argument("--system", help="baked-in system prompt (required for --shape persona)")
    args = ap.parse_args()

    name = args.name
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        die("name must be lowercase letters/digits/-/_ and start with a letter")
    mod = name.replace("-", "_")
    if args.shape == "persona" and not (args.model and args.system):
        die("--shape persona requires --model and --system")
    if args.shape == "image" and not args.model:
        die("--shape image requires --model")

    def esc(s):
        return (s or "").replace("\\\\", "\\\\\\\\").replace('"', '\\\\"')

    def sub(t):
        return (t.replace("__NAME__", name).replace("__MOD__", mod)
                .replace("__DESC__", args.desc)
                .replace("__MODEL__", args.model or "").replace("__SYSTEM__", esc(args.system)))

    print(f"Scaffolding intern '{name}' ({args.shape} shape):")
    adapter = {"api": ADAPTER_API, "cli": ADAPTER_CLI,
               "persona": ADAPTER_PERSONA, "image": ADAPTER_IMAGE}[args.shape]
    write(REPO / "kuli" / f"{mod}.py", sub(adapter))
    write(REPO / "kuli" / f"{mod}_batch.py", sub(BATCH))
    write(REPO / "bin" / f"ask-{name}", sub(LAUNCHER), executable=True)
    write(REPO / "bin" / f"ask-{name}-batch",
          sub(LAUNCHER).replace(f"kuli.{mod}", f"kuli.{mod}_batch")
          .replace(f"ask-{name} ", f"ask-{name}-batch "), executable=True)
    write(REPO / "skills" / name / "SKILL.md", sub(SKILL))

    steps = []
    if args.shape in ("api", "cli"):
        steps.append(f"Fill the `call_backend()` TODO in kuli/{mod}.py")
    steps += [
        f"Flesh out skills/{name}/SKILL.md",
        f"Add '{name}' to the skill loop in install.sh",
        f"(optional) add an ask_{mod} tool to mcp/server.py",
        f"bash install.sh && ask-{name} \"test\"",
    ]
    body = "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))
    print(f"\nDone. Next (manual):\n{body}\n")


if __name__ == "__main__":
    main()
