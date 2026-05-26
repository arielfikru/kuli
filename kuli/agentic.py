"""kuli.agentic — run an OpenRouter model through Codex's agentic harness.

DeepSeek/OpenRouter models are plain text APIs (no repo access, no edits). But
Codex's CLI harness can drive ANY OpenRouter model agentically (proven: it reads
a repo, calls tools, edits files). So `ask-deepseek --agentic` and
`ask-or --agentic` just shell out to `ask-codex --or-model <slug>` — one engine,
no duplicated harness logic. Needs OPENROUTER_API_KEY (no ChatGPT login).
"""
import shutil
import subprocess
import sys
from pathlib import Path


def _ask_codex():
    """Locate ask-codex: PATH first, then ~/.claude/bin (PATH may be unset)."""
    found = shutil.which("ask-codex")
    if found:
        return found
    fallback = Path.home() / ".claude" / "bin" / "ask-codex"
    return str(fallback) if fallback.exists() else None


def run(slug, prompt, apply, cd, timeout, prog):
    """Delegate an agentic coding task to the codex harness on model `slug`.
    Streams codex output straight through; returns its exit code."""
    cli = _ask_codex()
    if not cli:
        print(f"{prog}: ask-codex not found (needed for --agentic)", file=sys.stderr)
        sys.exit(1)
    cmd = [cli, "--or-model", slug]
    if apply:
        cmd.append("--apply")
    if cd:
        cmd += ["-C", cd]
    if timeout:
        cmd += ["--timeout", str(timeout)]
    cmd.append(prompt)
    try:
        return subprocess.run(cmd).returncode
    except KeyboardInterrupt:
        return 130
