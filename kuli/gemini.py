"""kuli.gemini — vision intern. Calls Gemini CLI headless for media analysis.

Backend: the `gemini` CLI run from an empty temp dir (so it does not auto-load
GEMINI.md / scan the workspace, which bloats input ~90k->8k tokens). Media is
copied into that dir and referenced with Gemini's `@basename` syntax, since
gemini sandboxes file reads to cwd. Stdlib only.
Env: GEMINI_MODEL / GEMINI_TIMEOUT (optional).
Exit codes: 0 ok, 1 usage/input error, 2 gemini error.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile

from . import core, health

PROG = "ask-gemini"
INTERN = "gemini"
DEFAULT_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "300"))
MODEL_PRO = "gemini-3.1-pro-preview"
MODEL_FLASH = "gemini-3-flash-preview"

die = core.make_die(PROG)


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Call Gemini CLI headless for analysis.")
    p.add_argument("prompt", nargs="*", help="prompt text (else/also read stdin)")
    p.add_argument("--file", "-f", action="append", default=[],
                   help="media/file to analyze (image, video, doc); repeatable")
    p.add_argument("--model", "-m", help="explicit Gemini model name")
    p.add_argument("--flash", action="store_true", help=f"fast/cheap model ({MODEL_FLASH})")
    p.add_argument("--pro", action="store_true", help=f"most capable model ({MODEL_PRO})")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"seconds before giving up (default {DEFAULT_TIMEOUT}, env GEMINI_TIMEOUT)")
    p.add_argument("--consistency", "-c", type=int, metavar="N",
                   help="self-consistency: sample N, majority-vote (discrete answers only)")
    p.add_argument("--raw", action="store_true", help="print full gemini JSON, not just .response")
    p.add_argument("--quiet", "-q", action="store_true", help="suppress usage stats on stderr")
    return p.parse_args()


def build_prompt(args):
    parts = []
    if args.prompt:
        parts.append(" ".join(args.prompt))
    piped = core.read_stdin()
    if piped:
        parts.append(piped)
    text = " ".join(parts).strip()
    if not text and not args.file:
        die("empty prompt (pass args, --file, or pipe stdin)", 1)
    return text


def resolve_files(paths):
    out = []
    for path in paths:
        ap = os.path.abspath(path)
        if not os.path.exists(ap):
            die(f"file not found: {path}", 1)
        out.append(ap)
    return out


def resolve_model(args):
    if args.model:
        return args.model
    if args.flash:
        return MODEL_FLASH
    if args.pro:
        return MODEL_PRO
    return os.environ.get("GEMINI_MODEL")


def stage_media(workdir, files):
    """Copy media into workdir, return @basename refs, de-duping name clashes."""
    refs, used = [], {}
    for src in files:
        base = os.path.basename(src)
        if base in used:
            stem, ext = os.path.splitext(base)
            base = f"{stem}_{used[base]}{ext}"
        used[os.path.basename(src)] = used.get(os.path.basename(src), 0) + 1
        shutil.copy2(src, os.path.join(workdir, base))
        refs.append(f"@{base}")
    return refs


def run_gemini(args, prompt, files, timeout):
    with tempfile.TemporaryDirectory(prefix="ask-gemini-") as workdir:
        refs = stage_media(workdir, files)
        full_prompt = (prompt + " " + " ".join(refs)).strip() if refs else prompt
        cmd = ["gemini", "-p", full_prompt, "--skip-trust", "-o", "json"]
        model = resolve_model(args)
        if model:
            cmd += ["-m", model]
        try:
            proc = subprocess.run(cmd, cwd=workdir, capture_output=True,
                                  text=True, timeout=timeout)
        except FileNotFoundError:
            die("gemini CLI not found on PATH", 2)
        except subprocess.TimeoutExpired:
            health.record_failure(INTERN, "timed out", 2)
            die(f"gemini timed out after {timeout}s", 2)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout)[:500]
        health.record_failure(INTERN, msg, 2)
        die(f"gemini exited {proc.returncode}: {msg}", 2)
    return proc.stdout


def analyze_once(args, prompt, files, timeout):
    """One Gemini call -> (response_text, parsed_json)."""
    try:
        data = json.loads(run_gemini(args, prompt, files, timeout))
    except json.JSONDecodeError:
        die("unparseable gemini output", 2)
    return data.get("response", ""), data


def format_usage(data):
    models = (data.get("stats") or {}).get("models") or {}
    if not models:
        return None
    name = next(iter(models))
    tok = models[name].get("tokens", {})
    return (f"[{name} | in {tok.get('input', '?')} out {tok.get('candidates', '?')} tok"
            f" | cached {tok.get('cached', 0)}]")


def main():
    args = parse_args()
    prompt = build_prompt(args)
    files = resolve_files(args.file)

    n = args.consistency
    if n and n > 1:
        response, votes, metas = core.run_consistency(
            lambda: analyze_once(args, prompt, files, args.timeout), n)
        data = metas[0]
    else:
        response, data = analyze_once(args, prompt, files, args.timeout)
        votes = None
    health.record_success(INTERN)
    if args.raw:
        print(json.dumps(data, indent=2))
    else:
        print(response)
    core.emit_stats(format_usage(data) or "", votes, n, args.quiet)


if __name__ == "__main__":
    main()
