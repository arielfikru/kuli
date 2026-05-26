"""kuli.recraft — SVG vector image generator (Recraft V4.1 Vector) — icons, logos, illustrations.

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

from . import core, health, openrouter

PROG = "ask-recraft"
INTERN = "recraft"
MODEL = "recraft/recraft-v4.1-vector"
STYLE = ""  # optional style preamble prepended to every prompt
die = core.make_die(PROG)

EXT = {"image/svg+xml": "svg", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def parse_args():
    p = argparse.ArgumentParser(prog=PROG, description="Generate SVG vector graphics.")
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
    data = openrouter.call_api(payload, key, args.timeout, die, PROG, INTERN)
    mime, blob = extract_image(data)
    out = args.out or f"{PROG}-{int(time.time() * 1000)}-{os.getpid()}.{EXT.get(mime, 'bin')}"
    with open(out, "wb") as fh:
        fh.write(blob)
    health.record_success(INTERN)
    print(os.path.abspath(out))
    usage = data.get("usage", {})
    core.emit_stats(openrouter.format_usage(MODEL, usage) if usage else "", None, None, args.quiet)


if __name__ == "__main__":
    main()
